from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..utils import encryption
from .models import (
    ConversationV2,
    FriendRequest,
    Friendship,
    Group,
    GroupSearchToken,
    GroupInvite,
    GroupJoinRequest,
    GroupMember,
    PrivateChatAccess,
    User,
    UserSearchToken,
)


def _sort_users_by_username(users: list[User]) -> list[User]:
    return sorted(users, key=lambda user: (encryption.normalize_search_text(user.username), user.id))


def _sort_groups_by_name(rows: list[tuple[Group, Optional[datetime]]]) -> list[tuple[Group, Optional[datetime]]]:
    return sorted(rows, key=lambda item: (encryption.normalize_search_text(item[0].name), item[0].id))


def _matches_keyword(value: str, keyword: str) -> bool:
    return encryption.normalize_search_text(keyword) in encryption.normalize_search_text(value)


def _replace_user_search_tokens(db: Session, user_id: int, username: str):
    db.query(UserSearchToken).filter(UserSearchToken.user_id == user_id).delete(synchronize_session=False)
    token_hashes = encryption.build_blind_index_hashes(username, namespace="user.search")
    if token_hashes:
        db.add_all([UserSearchToken(user_id=user_id, token_hash=token_hash) for token_hash in token_hashes])


def _replace_group_search_tokens(db: Session, group_id: int, group_name: str):
    db.query(GroupSearchToken).filter(GroupSearchToken.group_id == group_id).delete(synchronize_session=False)
    token_hashes = encryption.build_blind_index_hashes(group_name, namespace="group.search")
    if token_hashes:
        db.add_all([GroupSearchToken(group_id=group_id, token_hash=token_hash) for token_hash in token_hashes])


def _query_entity_ids_by_blind_index(db: Session, token_model, entity_column, token_hashes: list[str], candidate_ids: list[int] | None = None):
    if not token_hashes:
        return []

    query = db.query(entity_column).filter(token_model.token_hash.in_(token_hashes))
    if candidate_ids is not None:
        if not candidate_ids:
            return []
        query = query.filter(entity_column.in_(candidate_ids))

    rows = query.group_by(entity_column).having(
        func.count(func.distinct(token_model.token_hash)) == len(token_hashes)
    ).all()
    return [entity_id for entity_id, in rows]


def sync_user_search_tokens(db: Session, user_id: int, username: str):
    _replace_user_search_tokens(db, user_id, username)


def sync_group_search_tokens(db: Session, group_id: int, group_name: str):
    _replace_group_search_tokens(db, group_id, group_name)


def get_user_search_token_hashes(db: Session, user_id: int):
    rows = db.query(UserSearchToken.token_hash).filter(UserSearchToken.user_id == user_id).all()
    return {token_hash for token_hash, in rows}


def get_group_search_token_hashes(db: Session, group_id: int):
    rows = db.query(GroupSearchToken.token_hash).filter(GroupSearchToken.group_id == group_id).all()
    return {token_hash for token_hash, in rows}


def get_user_blind_index_candidate_ids(db: Session, keyword: str, candidate_user_ids: list[int] | None = None):
    token_hashes = encryption.build_blind_index_hashes(keyword, namespace="user.search")
    return _query_entity_ids_by_blind_index(db, UserSearchToken, UserSearchToken.user_id, token_hashes, candidate_user_ids)


def get_group_blind_index_candidate_ids(db: Session, keyword: str):
    token_hashes = encryption.build_blind_index_hashes(keyword, namespace="group.search")
    return _query_entity_ids_by_blind_index(db, GroupSearchToken, GroupSearchToken.group_id, token_hashes)


def get_user(db: Session, user_id: int):
    """通过 ID 获取用户。"""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str):
    """通过用户名获取用户。"""
    return db.query(User).filter(
        User.username_hash == encryption.metadata_hash(username, case_insensitive=True, namespace="user.username")
    ).first()


def create_group(db: Session, name: str, owner_id: int, member_ids: list[int]):
    """创建群组并写入成员关系。"""
    try:
        group = Group(name=name, owner_id=owner_id)
        db.add(group)
        db.flush()
        _replace_group_search_tokens(db, group.id, name)

        all_members = set(member_ids)
        all_members.add(owner_id)

        for uid in all_members:
            member = GroupMember(group_id=group.id, user_id=uid)
            db.add(member)

        db.commit()
        db.refresh(group)
        return group
    except Exception:
        db.rollback()
        raise


def get_group_members(db: Session, group_id: int):
    """获取群成员 ID 列表。"""
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    return [m.user_id for m in members]


def canonical_friendship_pair(user_a_id: int, user_b_id: int):
    """返回按固定顺序排列的好友关系主键对。"""
    return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)


def friend_request_pair_key(user_a_id: int, user_b_id: int):
    """返回好友请求使用的标准化配对键。"""
    user_one_id, user_two_id = canonical_friendship_pair(user_a_id, user_b_id)
    return f"{user_one_id}:{user_two_id}"


def _delete_conflicting_friend_requests(db: Session, pair_key: str, target_status: str, exclude_request_id: int):
    """删除同配对下会与目标状态冲突的历史请求。"""
    db.query(FriendRequest).filter(
        FriendRequest.pair_key == pair_key,
        FriendRequest.status == target_status,
        FriendRequest.id != exclude_request_id,
    ).delete(synchronize_session=False)


def _delete_conflicting_group_invites(db: Session, group_id: int, invitee_id: int, target_status: str, exclude_invite_id: int):
    """删除会与群邀请目标状态冲突的历史记录。"""
    db.query(GroupInvite).filter(
        GroupInvite.group_id == group_id,
        GroupInvite.invitee_id == invitee_id,
        GroupInvite.status == target_status,
        GroupInvite.id != exclude_invite_id,
    ).delete(synchronize_session=False)


def _delete_conflicting_group_join_requests(db: Session, group_id: int, requester_id: int, target_status: str, exclude_request_id: int):
    """删除会与入群申请目标状态冲突的历史记录。"""
    db.query(GroupJoinRequest).filter(
        GroupJoinRequest.group_id == group_id,
        GroupJoinRequest.requester_id == requester_id,
        GroupJoinRequest.status == target_status,
        GroupJoinRequest.id != exclude_request_id,
    ).delete(synchronize_session=False)


def get_friendship(db: Session, user_a_id: int, user_b_id: int):
    """获取两人之间的好友关系。"""
    user_one_id, user_two_id = canonical_friendship_pair(user_a_id, user_b_id)
    return db.query(Friendship).filter(
        Friendship.user_one_id == user_one_id,
        Friendship.user_two_id == user_two_id
    ).first()


def get_private_chat_access(db: Session, user_a_id: int, user_b_id: int):
    """获取两人之间的私聊访问覆盖状态。"""
    user_one_id, user_two_id = canonical_friendship_pair(user_a_id, user_b_id)
    return db.query(PrivateChatAccess).filter(
        PrivateChatAccess.user_one_id == user_one_id,
        PrivateChatAccess.user_two_id == user_two_id
    ).first()


def set_private_chat_access(db: Session, user_a_id: int, user_b_id: int, is_enabled: bool):
    """创建或更新两人之间的私聊访问覆盖状态。"""
    user_one_id, user_two_id = canonical_friendship_pair(user_a_id, user_b_id)
    access = get_private_chat_access(db, user_a_id, user_b_id)

    if access is None:
        access = PrivateChatAccess(
            user_one_id=user_one_id,
            user_two_id=user_two_id,
            is_enabled=is_enabled
        )
        db.add(access)
    else:
        access.is_enabled = is_enabled

    db.commit()
    db.refresh(access)
    return access


def list_friendships_for_user(db: Session, user_id: int):
    """获取用户的全部好友关系记录。"""
    return db.query(Friendship).filter(
        or_(Friendship.user_one_id == user_id, Friendship.user_two_id == user_id)
    ).all()


def get_friend_ids(db: Session, user_id: int):
    """获取当前用户的好友 ID 集合。"""
    friend_ids = set()
    for friendship in list_friendships_for_user(db, user_id):
        friend_ids.add(friendship.user_two_id if friendship.user_one_id == user_id else friendship.user_one_id)
    return friend_ids


def get_friend_relationship_map(db: Session, current_user_id: int, target_user_ids: list[int]):
    """获取当前用户与目标用户之间的好友/请求状态。"""
    relationship_map = {
        target_user_id: {
            "relationship_status": "none",
            "friend_request_id": None
        }
        for target_user_id in target_user_ids
    }

    if not target_user_ids:
        return relationship_map

    friendships = db.query(Friendship).filter(
        or_(
            and_(Friendship.user_one_id == current_user_id, Friendship.user_two_id.in_(target_user_ids)),
            and_(Friendship.user_two_id == current_user_id, Friendship.user_one_id.in_(target_user_ids))
        )
    ).all()

    for friendship in friendships:
        friend_id = friendship.user_two_id if friendship.user_one_id == current_user_id else friendship.user_one_id
        if friend_id in relationship_map:
            relationship_map[friend_id] = {
                "relationship_status": "friend",
                "friend_request_id": None
            }

    pending_requests = db.query(FriendRequest).filter(
        FriendRequest.status == "pending",
        or_(
            and_(FriendRequest.sender_id == current_user_id, FriendRequest.receiver_id.in_(target_user_ids)),
            and_(FriendRequest.receiver_id == current_user_id, FriendRequest.sender_id.in_(target_user_ids))
        )
    ).all()

    for friend_request in pending_requests:
        target_user_id = friend_request.receiver_id if friend_request.sender_id == current_user_id else friend_request.sender_id
        if target_user_id not in relationship_map:
            continue
        if relationship_map[target_user_id]["relationship_status"] == "friend":
            continue

        relationship_map[target_user_id] = {
            "relationship_status": "outgoing_pending" if friend_request.sender_id == current_user_id else "incoming_pending",
            "friend_request_id": friend_request.id
        }

    return relationship_map


def get_group_access_state_map(db: Session, current_user_id: int, group_ids: list[int]):
    """获取当前用户对指定群组的邀请/申请状态。"""
    access_map = {
        group_id: {
            "invite_status": None,
            "invite_id": None,
            "join_request_status": None,
            "join_request_id": None,
        }
        for group_id in group_ids
    }

    if not group_ids:
        return access_map

    invites = db.query(GroupInvite).filter(
        GroupInvite.invitee_id == current_user_id,
        GroupInvite.group_id.in_(group_ids),
        GroupInvite.status == "pending"
    ).all()
    for invite in invites:
        access_map[invite.group_id] = {
            **access_map[invite.group_id],
            "invite_status": invite.status,
            "invite_id": invite.id,
        }

    join_requests = db.query(GroupJoinRequest).filter(
        GroupJoinRequest.requester_id == current_user_id,
        GroupJoinRequest.group_id.in_(group_ids),
        GroupJoinRequest.status == "pending"
    ).all()
    for join_request in join_requests:
        access_map[join_request.group_id] = {
            **access_map[join_request.group_id],
            "join_request_status": join_request.status,
            "join_request_id": join_request.id,
        }

    return access_map


def get_pending_friend_request_between(db: Session, user_a_id: int, user_b_id: int):
    """获取两人之间仍在待处理的好友请求。"""
    pair_key = friend_request_pair_key(user_a_id, user_b_id)
    return db.query(FriendRequest).filter(
        FriendRequest.pair_key == pair_key,
        FriendRequest.status == "pending"
    ).first()


def create_friend_request(db: Session, sender_id: int, receiver_id: int):
    """创建好友请求。"""
    request = FriendRequest(
        sender_id=sender_id,
        receiver_id=receiver_id,
        pair_key=friend_request_pair_key(sender_id, receiver_id),
        status="pending"
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def get_friend_request(db: Session, request_id: int):
    """按 ID 获取好友请求。"""
    return db.query(FriendRequest).filter(FriendRequest.id == request_id).first()


def list_received_friend_requests(db: Session, user_id: int, status: str = "pending"):
    """获取当前用户收到的好友请求。"""
    return db.query(FriendRequest).filter(
        FriendRequest.receiver_id == user_id,
        FriendRequest.status == status
    ).order_by(FriendRequest.created_at.desc()).all()


def list_sent_friend_requests(db: Session, user_id: int, status: str = "pending"):
    """获取当前用户发出的好友请求。"""
    return db.query(FriendRequest).filter(
        FriendRequest.sender_id == user_id,
        FriendRequest.status == status
    ).order_by(FriendRequest.created_at.desc()).all()


def update_friend_request_status(db: Session, friend_request: FriendRequest, status: str):
    """更新好友请求状态。"""
    _delete_conflicting_friend_requests(db, friend_request.pair_key, status, friend_request.id)
    friend_request.status = status
    friend_request.responded_at = datetime.now()
    db.commit()
    db.refresh(friend_request)
    return friend_request


def create_friendship(db: Session, user_a_id: int, user_b_id: int):
    """创建好友关系。"""
    user_one_id, user_two_id = canonical_friendship_pair(user_a_id, user_b_id)
    friendship = Friendship(user_one_id=user_one_id, user_two_id=user_two_id)
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return friendship


def accept_friend_request(db: Session, friend_request: FriendRequest):
    """接受好友请求并建立好友关系。"""
    try:
        _delete_conflicting_friend_requests(db, friend_request.pair_key, "accepted", friend_request.id)
        friend_request.status = "accepted"
        friend_request.responded_at = datetime.now()

        friendship = get_friendship(db, friend_request.sender_id, friend_request.receiver_id)
        if friendship is None:
            user_one_id, user_two_id = canonical_friendship_pair(friend_request.sender_id, friend_request.receiver_id)
            friendship = Friendship(user_one_id=user_one_id, user_two_id=user_two_id)
            db.add(friendship)

        db.commit()
        db.refresh(friend_request)
        if friendship is not None:
            db.refresh(friendship)
        return friendship
    except Exception:
        db.rollback()
        raise


def accept_friend_request_with_chat_access(db: Session, friend_request: FriendRequest):
    """在一次事务中接受好友请求并启用私聊访问。"""
    try:
        _delete_conflicting_friend_requests(db, friend_request.pair_key, "accepted", friend_request.id)
        friend_request.status = "accepted"
        friend_request.responded_at = datetime.now()

        friendship = get_friendship(db, friend_request.sender_id, friend_request.receiver_id)
        if friendship is None:
            user_one_id, user_two_id = canonical_friendship_pair(friend_request.sender_id, friend_request.receiver_id)
            friendship = Friendship(user_one_id=user_one_id, user_two_id=user_two_id)
            db.add(friendship)

        access = get_private_chat_access(db, friend_request.sender_id, friend_request.receiver_id)
        if access is None:
            user_one_id, user_two_id = canonical_friendship_pair(friend_request.sender_id, friend_request.receiver_id)
            access = PrivateChatAccess(user_one_id=user_one_id, user_two_id=user_two_id, is_enabled=True)
            db.add(access)
        else:
            access.is_enabled = True

        db.commit()
        db.refresh(friend_request)
        if friendship is not None:
            db.refresh(friendship)
        db.refresh(access)
        return friendship
    except Exception:
        db.rollback()
        raise


def delete_friendship(db: Session, user_a_id: int, user_b_id: int):
    """删除好友关系。"""
    friendship = get_friendship(db, user_a_id, user_b_id)
    if not friendship:
        return False

    db.delete(friendship)
    db.commit()
    return True


def delete_friendship_and_disable_chat(db: Session, user_a_id: int, user_b_id: int):
    """在一次事务中删除好友关系并禁用私聊访问。"""
    friendship = get_friendship(db, user_a_id, user_b_id)
    if not friendship:
        return False

    try:
        db.delete(friendship)

        access = get_private_chat_access(db, user_a_id, user_b_id)
        if access is None:
            user_one_id, user_two_id = canonical_friendship_pair(user_a_id, user_b_id)
            access = PrivateChatAccess(user_one_id=user_one_id, user_two_id=user_two_id, is_enabled=False)
            db.add(access)
        else:
            access.is_enabled = False

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def get_pending_group_invite(db: Session, group_id: int, invitee_id: int):
    """获取群组的待处理邀请。"""
    return db.query(GroupInvite).filter(
        GroupInvite.group_id == group_id,
        GroupInvite.invitee_id == invitee_id,
        GroupInvite.status == "pending"
    ).first()


def create_group_invite(db: Session, group_id: int, inviter_id: int, invitee_id: int):
    """创建群邀请。"""
    invite = GroupInvite(
        group_id=group_id,
        inviter_id=inviter_id,
        invitee_id=invitee_id,
        status="pending"
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def create_group_invites_batch(db: Session, group_id: int, inviter_id: int, invitee_ids: list[int]):
    """以单事务批量创建群邀请。"""
    try:
        invites = [
            GroupInvite(
                group_id=group_id,
                inviter_id=inviter_id,
                invitee_id=invitee_id,
                status="pending"
            )
            for invitee_id in invitee_ids
        ]
        db.add_all(invites)
        db.commit()
        for invite in invites:
            db.refresh(invite)
        return invites
    except Exception:
        db.rollback()
        raise


def get_group_invite(db: Session, invite_id: int):
    """按 ID 获取群邀请。"""
    return db.query(GroupInvite).filter(GroupInvite.id == invite_id).first()


def list_received_group_invites(db: Session, user_id: int, status: str = "pending"):
    """获取当前用户收到的群邀请。"""
    return db.query(GroupInvite).filter(
        GroupInvite.invitee_id == user_id,
        GroupInvite.status == status
    ).order_by(GroupInvite.created_at.desc()).all()


def list_group_invites_for_group(db: Session, group_id: int, status: str = "pending"):
    """获取群组发出的邀请列表。"""
    return db.query(GroupInvite).filter(
        GroupInvite.group_id == group_id,
        GroupInvite.status == status
    ).order_by(GroupInvite.created_at.desc()).all()


def update_group_invite_status(db: Session, invite: GroupInvite, status: str):
    """更新群邀请状态。"""
    _delete_conflicting_group_invites(db, invite.group_id, invite.invitee_id, status, invite.id)
    invite.status = status
    invite.responded_at = datetime.now()
    db.commit()
    db.refresh(invite)
    return invite


def cancel_pending_group_join_requests(db: Session, group_id: int, requester_id: int):
    """取消同一群组的其他待处理入群申请。"""
    requests = db.query(GroupJoinRequest).filter(
        GroupJoinRequest.group_id == group_id,
        GroupJoinRequest.requester_id == requester_id,
        GroupJoinRequest.status == "pending"
    ).all()
    for join_request in requests:
        _delete_conflicting_group_join_requests(db, group_id, requester_id, "cancelled", join_request.id)
        join_request.status = "cancelled"
        join_request.responded_at = datetime.now()


def cancel_pending_group_invites(db: Session, group_id: int, invitee_id: int):
    """取消同一群组的其他待处理邀请。"""
    invites = db.query(GroupInvite).filter(
        GroupInvite.group_id == group_id,
        GroupInvite.invitee_id == invitee_id,
        GroupInvite.status == "pending"
    ).all()
    for invite in invites:
        _delete_conflicting_group_invites(db, group_id, invitee_id, "cancelled", invite.id)
        invite.status = "cancelled"
        invite.responded_at = datetime.now()


def accept_group_invite(db: Session, invite: GroupInvite):
    """接受群邀请并加入群组。"""
    try:
        _delete_conflicting_group_invites(db, invite.group_id, invite.invitee_id, "accepted", invite.id)
        invite.status = "accepted"
        invite.responded_at = datetime.now()
        cancel_pending_group_join_requests(db, invite.group_id, invite.invitee_id)

        exists = db.query(GroupMember).filter_by(group_id=invite.group_id, user_id=invite.invitee_id).first()
        if not exists:
            member = GroupMember(group_id=invite.group_id, user_id=invite.invitee_id)
            db.add(member)

        db.commit()
        db.refresh(invite)
        return invite
    except Exception:
        db.rollback()
        raise


def get_pending_group_join_request(db: Session, group_id: int, requester_id: int):
    """获取待处理的入群申请。"""
    return db.query(GroupJoinRequest).filter(
        GroupJoinRequest.group_id == group_id,
        GroupJoinRequest.requester_id == requester_id,
        GroupJoinRequest.status == "pending"
    ).first()


def create_group_join_request(db: Session, group_id: int, requester_id: int, note: Optional[str] = None):
    """创建入群申请。"""
    join_request = GroupJoinRequest(
        group_id=group_id,
        requester_id=requester_id,
        note=note,
        status="pending"
    )
    db.add(join_request)
    db.commit()
    db.refresh(join_request)
    return join_request


def get_group_join_request(db: Session, request_id: int):
    """按 ID 获取入群申请。"""
    return db.query(GroupJoinRequest).filter(GroupJoinRequest.id == request_id).first()


def list_group_join_requests_for_group(db: Session, group_id: int, status: str = "pending"):
    """获取群组收到的入群申请。"""
    return db.query(GroupJoinRequest).filter(
        GroupJoinRequest.group_id == group_id,
        GroupJoinRequest.status == status
    ).order_by(GroupJoinRequest.created_at.desc()).all()


def list_owned_group_join_requests(db: Session, owner_id: int, status: str = "pending"):
    """获取当前用户作为群主收到的入群申请。"""
    owned_group_ids = db.query(Group.id).filter(Group.owner_id == owner_id).all()
    group_ids = [group_id for group_id, in owned_group_ids]
    if not group_ids:
        return []

    return db.query(GroupJoinRequest).filter(
        GroupJoinRequest.group_id.in_(group_ids),
        GroupJoinRequest.status == status
    ).order_by(GroupJoinRequest.created_at.desc()).all()


def list_sent_group_join_requests(db: Session, user_id: int, status: str = "pending"):
    """获取当前用户发出的入群申请。"""
    return db.query(GroupJoinRequest).filter(
        GroupJoinRequest.requester_id == user_id,
        GroupJoinRequest.status == status
    ).order_by(GroupJoinRequest.created_at.desc()).all()


def update_group_join_request_status(db: Session, join_request: GroupJoinRequest, status: str):
    """更新入群申请状态。"""
    _delete_conflicting_group_join_requests(db, join_request.group_id, join_request.requester_id, status, join_request.id)
    join_request.status = status
    join_request.responded_at = datetime.now()
    db.commit()
    db.refresh(join_request)
    return join_request


def approve_group_join_request(db: Session, join_request: GroupJoinRequest):
    """批准入群申请并添加成员。"""
    try:
        _delete_conflicting_group_join_requests(db, join_request.group_id, join_request.requester_id, "approved", join_request.id)
        join_request.status = "approved"
        join_request.responded_at = datetime.now()
        cancel_pending_group_invites(db, join_request.group_id, join_request.requester_id)

        exists = db.query(GroupMember).filter_by(group_id=join_request.group_id, user_id=join_request.requester_id).first()
        if not exists:
            member = GroupMember(group_id=join_request.group_id, user_id=join_request.requester_id)
            db.add(member)

        db.commit()
        db.refresh(join_request)
        return join_request
    except Exception:
        db.rollback()
        raise


def get_related_user_ids(db: Session, user_id: int):
    """获取与当前用户存在私聊或共同群组关系的用户 ID。"""
    related_ids = set(get_private_partner_ids(db, user_id))

    group_ids = db.query(GroupMember.group_id).filter(GroupMember.user_id == user_id).all()
    if group_ids:
        member_rows = db.query(GroupMember.user_id).filter(
            GroupMember.group_id.in_([group_id for group_id, in group_ids])
        ).all()
        related_ids.update(member_id for member_id, in member_rows if member_id != user_id)

    return related_ids


def get_private_partner_ids(db: Session, user_id: int):
    """获取与当前用户存在私聊历史的用户 ID。"""
    partner_ids = set()
    conversation_pairs = db.query(
        ConversationV2.pair_user_low_id,
        ConversationV2.pair_user_high_id,
    ).filter(
        ConversationV2.conversation_type == "private",
        or_(
            ConversationV2.pair_user_low_id == user_id,
            ConversationV2.pair_user_high_id == user_id,
        ),
    ).all()

    for low_id, high_id in conversation_pairs:
        other_id = high_id if low_id == user_id else low_id
        if other_id and other_id != user_id:
            partner_ids.add(other_id)

    return partner_ids


def has_private_conversation(db: Session, user_a_id: int, user_b_id: int):
    """判断两人是否已有私聊历史。"""
    user_one_id, user_two_id = canonical_friendship_pair(user_a_id, user_b_id)
    return db.query(ConversationV2.id).filter(
        ConversationV2.conversation_type == "private",
        ConversationV2.pair_user_low_id == user_one_id,
        ConversationV2.pair_user_high_id == user_two_id,
    ).first() is not None


def can_start_private_chat(db: Session, user_a_id: int, user_b_id: int):
    """判断是否允许发起新的私聊。"""
    access = get_private_chat_access(db, user_a_id, user_b_id)
    if access is not None:
        return access.is_enabled

    return get_friendship(db, user_a_id, user_b_id) is not None or has_private_conversation(db, user_a_id, user_b_id)


def search_friends(db: Session, current_user_id: int, keyword: str, limit: int = 20, offset: int = 0):
    """按用户名在好友范围内搜索。"""
    normalized = keyword.strip()
    friend_ids = list(get_friend_ids(db, current_user_id))
    if not normalized or not friend_ids:
        return []

    candidate_ids = get_user_blind_index_candidate_ids(db, normalized, candidate_user_ids=friend_ids)
    matched_users = [
        user for user in db.query(User).filter(User.id.in_(candidate_ids)).all()
        if _matches_keyword(user.username, normalized)
    ]
    sorted_users = _sort_users_by_username(matched_users)
    return sorted_users[offset: offset + limit + 1]


def search_users(db: Session, current_user_id: int, keyword: str, limit: int = 20, offset: int = 0):
    """按用户名模糊搜索用户。"""
    normalized = keyword.strip()
    if not normalized:
        return []

    candidate_ids = get_user_blind_index_candidate_ids(db, normalized)
    matched_users = [
        user for user in db.query(User).filter(User.id.in_(candidate_ids), User.id != current_user_id).all()
        if _matches_keyword(user.username, normalized)
    ]
    sorted_users = _sort_users_by_username(matched_users)
    return sorted_users[offset: offset + limit + 1]


def search_groups(db: Session, keyword: str, limit: int = 20, offset: int = 0, anchor_time: Optional[datetime] = None):
    """按群组名称模糊搜索群组。"""
    normalized = keyword.strip()
    if not normalized:
        return []

    candidate_ids = get_group_blind_index_candidate_ids(db, normalized)
    if not candidate_ids:
        return []

    query = db.query(Group, ConversationV2.last_message_at).outerjoin(
        ConversationV2,
        and_(
            ConversationV2.group_id == Group.id,
            ConversationV2.conversation_type == "group",
        )
    ).filter(Group.id.in_(candidate_ids))

    if anchor_time is not None:
        query = query.filter(
            or_(
                ConversationV2.last_message_at.is_(None),
                ConversationV2.last_message_at <= anchor_time,
            )
        )

    rows = query.all()

    matched_rows = [row for row in rows if _matches_keyword(row[0].name, normalized)]
    matched_rows.sort(
        key=lambda item: (
            item[1] is None,
            -(item[1].timestamp() if item[1] is not None else 0),
            encryption.normalize_search_text(item[0].name),
            item[0].id,
        )
    )
    return matched_rows[offset: offset + limit + 1]


def update_group_name(db: Session, group_id: int, new_name: str):
    group = db.query(Group).filter(Group.id == group_id).first()
    if group:
        group.name = new_name
        _replace_group_search_tokens(db, group_id, new_name)
        db.commit()
        db.refresh(group)
    return group


def update_group_avatar(db: Session, group_id: int, avatar: str | None):
    group = db.query(Group).filter(Group.id == group_id).first()
    if group:
        group.avatar = avatar
        db.commit()
        db.refresh(group)
    return group


def delete_group(db: Session, group_id: int):
    group = db.query(Group).filter(Group.id == group_id).first()
    if group:
        db.delete(group)
        db.commit()
        return True
    return False


def get_group(db: Session, group_id: int):
    return db.query(Group).filter(Group.id == group_id).first()


def get_group_members_detailed(db: Session, group_id: int):
    """通过联表查询返回群成员详情。"""
    return db.query(User).join(
        GroupMember, User.id == GroupMember.user_id
    ).filter(GroupMember.group_id == group_id).all()


def add_group_member(db: Session, group_id: int, user_id: int):
    """邀请新成员。"""
    exists = db.query(GroupMember).filter_by(group_id=group_id, user_id=user_id).first()
    if not exists:
        member = GroupMember(group_id=group_id, user_id=user_id)
        db.add(member)
        db.commit()
        return True
    return False


def remove_group_member(db: Session, group_id: int, user_id: int):
    """移除成员。"""
    member = db.query(GroupMember).filter_by(group_id=group_id, user_id=user_id).first()
    if member:
        db.delete(member)
        db.commit()
        return True
    return False


