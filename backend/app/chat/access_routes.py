import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import crud, get_db
from ..database.models import User
from ..e2ee.service import rotate_group_sender_key_epoch
from ..user.dependencies import get_current_user
from ..utils.log_utils import log_event
from .manager import manager as chat_manager
from .access_schemas import (
    ChatUserSummary,
    GroupInviteCreate,
    GroupInviteListResponse,
    GroupInviteSummary,
    GroupJoinRequestCreate,
    GroupJoinRequestListResponse,
    GroupJoinRequestSummary,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_group_invite_summary(db: Session, invite) -> GroupInviteSummary:
    group = crud.get_group(db, invite.group_id)
    inviter = crud.get_user(db, invite.inviter_id)
    invitee = crud.get_user(db, invite.invitee_id)
    return GroupInviteSummary(
        id=invite.id,
        group_id=invite.group_id,
        group_name=group.name,
        group_avatar=group.avatar,
        status=invite.status,
        created_at=invite.created_at,
        responded_at=invite.responded_at,
        inviter=ChatUserSummary(id=inviter.id, username=inviter.username, avatar=inviter.avatar),
        invitee=ChatUserSummary(id=invitee.id, username=invitee.username, avatar=invitee.avatar),
    )


def _build_join_request_summary(db: Session, join_request) -> GroupJoinRequestSummary:
    group = crud.get_group(db, join_request.group_id)
    requester = crud.get_user(db, join_request.requester_id)
    return GroupJoinRequestSummary(
        id=join_request.id,
        group_id=join_request.group_id,
        group_name=group.name,
        group_avatar=group.avatar,
        status=join_request.status,
        note=join_request.note,
        created_at=join_request.created_at,
        responded_at=join_request.responded_at,
        requester=ChatUserSummary(id=requester.id, username=requester.username, avatar=requester.avatar),
    )


@router.get("/group/invites", response_model=GroupInviteListResponse)
async def list_received_group_invites(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """返回当前用户收到的待处理群邀请。"""
    invites = crud.list_received_group_invites(db, current_user.id)
    return GroupInviteListResponse(
        items=[_build_group_invite_summary(db, invite) for invite in invites]
    )


@router.get("/group/{group_id}/invites", response_model=GroupInviteListResponse)
async def list_group_invites_for_group(
        group_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """返回某群组已发出的待处理邀请。"""
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以查看群邀请")

    invites = crud.list_group_invites_for_group(db, group_id)
    return GroupInviteListResponse(
        items=[_build_group_invite_summary(db, invite) for invite in invites]
    )


@router.post("/group/{group_id}/invites")
async def create_group_invite(
        group_id: int,
        payload: GroupInviteCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """创建群邀请记录。"""
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以发送群邀请")
    if payload.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能邀请自己")
    if not crud.get_user(db, payload.user_id):
        raise HTTPException(status_code=404, detail="目标用户不存在")
    if payload.user_id not in crud.get_friend_ids(db, current_user.id):
        raise HTTPException(status_code=400, detail="只能邀请好友入群")
    if payload.user_id in crud.get_group_members(db, group_id):
        raise HTTPException(status_code=400, detail="该用户已在群组中")
    if crud.get_pending_group_invite(db, group_id, payload.user_id):
        raise HTTPException(status_code=400, detail="该用户已有待处理群邀请")
    if crud.get_pending_group_join_request(db, group_id, payload.user_id):
        raise HTTPException(status_code=400, detail="该用户已有待处理入群申请")

    try:
        invite = crud.create_group_invite(db, group_id, current_user.id, payload.user_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该用户已有待处理群邀请")

    try:
        await chat_manager.broadcast_group_access_updated([current_user.id, payload.user_id], group_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "group_access_broadcast_failed", group_id=group_id, error=str(exc))

    return {"message": "群邀请已创建", "invite_id": invite.id}


@router.post("/group/invites/{invite_id}/accept")
async def accept_group_invite(
        invite_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """接受群邀请并加入群组。"""
    invite = crud.get_group_invite(db, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="群邀请不存在")
    if invite.invitee_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权处理该群邀请")
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="该群邀请已处理")

    try:
        crud.accept_group_invite(db, invite)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该用户已在群组中")

    group = crud.get_group(db, invite.group_id)
    member_ids = crud.get_group_members(db, invite.group_id)
    epoch = rotate_group_sender_key_epoch(db, invite.group_id, current_user.id)
    await chat_manager.broadcast_group_created(group.id, group.name, member_ids)
    await chat_manager.broadcast_group_epoch_changed(member_ids, invite.group_id, epoch.epoch)
    try:
        await chat_manager.broadcast_group_access_updated([invite.inviter_id, invite.invitee_id], invite.group_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "group_access_broadcast_failed", group_id=invite.group_id, error=str(exc))

    return {"message": "群邀请已接受"}


@router.post("/group/invites/{invite_id}/reject")
async def reject_group_invite(
        invite_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """拒绝群邀请。"""
    invite = crud.get_group_invite(db, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="群邀请不存在")
    if invite.invitee_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权处理该群邀请")
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="该群邀请已处理")

    crud.update_group_invite_status(db, invite, "rejected")
    try:
        await chat_manager.broadcast_group_access_updated([invite.inviter_id, invite.invitee_id], invite.group_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "group_access_broadcast_failed", group_id=invite.group_id, error=str(exc))
    return {"message": "群邀请已拒绝"}


@router.post("/group/{group_id}/join-requests")
async def create_group_join_request(
        group_id: int,
        payload: GroupJoinRequestCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """创建入群申请。"""
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if current_user.id in crud.get_group_members(db, group_id):
        raise HTTPException(status_code=400, detail="你已在该群组中")
    if crud.get_pending_group_join_request(db, group_id, current_user.id):
        raise HTTPException(status_code=400, detail="你已有待处理的入群申请")
    if crud.get_pending_group_invite(db, group_id, current_user.id):
        raise HTTPException(status_code=400, detail="你已收到该群组邀请")

    try:
        join_request = crud.create_group_join_request(db, group_id, current_user.id, payload.note)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="你已有待处理的入群申请")

    try:
        await chat_manager.broadcast_group_access_updated([current_user.id, group.owner_id], group_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "group_access_broadcast_failed", group_id=group_id, error=str(exc))

    return {"message": "入群申请已提交", "request_id": join_request.id}


@router.get("/group/{group_id}/join-requests", response_model=GroupJoinRequestListResponse)
async def list_group_join_requests(
        group_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """返回某群组收到的待处理入群申请。"""
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以查看入群申请")

    requests = crud.list_group_join_requests_for_group(db, group_id)
    return GroupJoinRequestListResponse(
        items=[_build_join_request_summary(db, item) for item in requests]
    )


@router.get("/group/join-requests/mine", response_model=GroupJoinRequestListResponse)
async def list_my_group_join_requests(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """返回当前用户发出的待处理入群申请。"""
    requests = crud.list_sent_group_join_requests(db, current_user.id)
    return GroupJoinRequestListResponse(
        items=[_build_join_request_summary(db, item) for item in requests]
    )


@router.get("/group/join-requests/owned", response_model=GroupJoinRequestListResponse)
async def list_owned_group_join_requests(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """返回当前用户作为群主收到的待处理入群申请。"""
    requests = crud.list_owned_group_join_requests(db, current_user.id)
    return GroupJoinRequestListResponse(
        items=[_build_join_request_summary(db, item) for item in requests]
    )


@router.post("/group/join-requests/{request_id}/approve")
async def approve_group_join_request(
        request_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """批准入群申请。"""
    join_request = crud.get_group_join_request(db, request_id)
    if not join_request:
        raise HTTPException(status_code=404, detail="入群申请不存在")

    group = crud.get_group(db, join_request.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以处理入群申请")
    if join_request.status != "pending":
        raise HTTPException(status_code=400, detail="该入群申请已处理")

    try:
        crud.approve_group_join_request(db, join_request)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该用户已在群组中")

    member_ids = crud.get_group_members(db, join_request.group_id)
    epoch = rotate_group_sender_key_epoch(db, join_request.group_id, current_user.id)
    await chat_manager.broadcast_group_created(group.id, group.name, member_ids)
    await chat_manager.broadcast_group_epoch_changed(member_ids, join_request.group_id, epoch.epoch)
    try:
        await chat_manager.broadcast_group_access_updated([join_request.requester_id, current_user.id], join_request.group_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "group_access_broadcast_failed", group_id=join_request.group_id, error=str(exc))

    return {"message": "入群申请已批准"}


@router.post("/group/join-requests/{request_id}/reject")
async def reject_group_join_request(
        request_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """拒绝入群申请。"""
    join_request = crud.get_group_join_request(db, request_id)
    if not join_request:
        raise HTTPException(status_code=404, detail="入群申请不存在")

    group = crud.get_group(db, join_request.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以处理入群申请")
    if join_request.status != "pending":
        raise HTTPException(status_code=400, detail="该入群申请已处理")

    crud.update_group_join_request_status(db, join_request, "rejected")
    try:
        await chat_manager.broadcast_group_access_updated([join_request.requester_id, current_user.id], join_request.group_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "group_access_broadcast_failed", group_id=join_request.group_id, error=str(exc))
    return {"message": "入群申请已拒绝"}


@router.delete("/group/join-requests/{request_id}")
async def cancel_group_join_request(
        request_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """取消当前用户发出的入群申请。"""
    join_request = crud.get_group_join_request(db, request_id)
    if not join_request:
        raise HTTPException(status_code=404, detail="入群申请不存在")
    if join_request.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权取消该入群申请")
    if join_request.status != "pending":
        raise HTTPException(status_code=400, detail="该入群申请已处理")

    group = crud.get_group(db, join_request.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    crud.update_group_join_request_status(db, join_request, "cancelled")
    try:
        await chat_manager.broadcast_group_access_updated([join_request.requester_id, group.owner_id], join_request.group_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "group_access_broadcast_failed", group_id=join_request.group_id, error=str(exc))
    return {"message": "入群申请已取消"}


@router.delete("/group/invites/{invite_id}")
async def cancel_group_invite(
        invite_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """取消群主发出的待处理邀请。"""
    invite = crud.get_group_invite(db, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="群邀请不存在")

    group = crud.get_group(db, invite.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以取消群邀请")
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="该群邀请已处理")

    crud.update_group_invite_status(db, invite, "cancelled")
    try:
        await chat_manager.broadcast_group_access_updated([invite.inviter_id, invite.invitee_id], invite.group_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "group_access_broadcast_failed", group_id=invite.group_id, error=str(exc))
    return {"message": "群邀请已取消"}
