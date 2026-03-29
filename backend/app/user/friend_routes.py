import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..chat.manager import manager as chat_manager
from ..database import crud, get_db
from ..database.models import User
from ..utils.log_utils import log_event
from .dependencies import get_current_user
from .friend_schemas import FriendRequestCreate, FriendRequestListResponse, FriendRequestSummary, FriendSummary, FriendUserSummary

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_friend_summary(db: Session, friendship, current_user_id: int) -> FriendSummary:
    friend_id = friendship.user_two_id if friendship.user_one_id == current_user_id else friendship.user_one_id
    friend = crud.get_user(db, friend_id)
    return FriendSummary(
        id=friend.id,
        username=friend.username,
        created_at=friendship.created_at
    )


def _build_friend_request_summary(db: Session, friend_request, perspective: str) -> FriendRequestSummary:
    target_id = friend_request.sender_id if perspective == "incoming" else friend_request.receiver_id
    target_user = crud.get_user(db, target_id)
    return FriendRequestSummary(
        id=friend_request.id,
        status=friend_request.status,
        created_at=friend_request.created_at,
        responded_at=friend_request.responded_at,
        user=FriendUserSummary(id=target_user.id, username=target_user.username)
    )


@router.get("/friends", response_model=list[FriendSummary])
async def list_friends(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """返回当前用户的好友列表。"""
    friendships = crud.list_friendships_for_user(db, current_user.id)
    return [_build_friend_summary(db, friendship, current_user.id) for friendship in friendships]


@router.get("/friends/search")
async def search_friends(
        q: str = Query(..., min_length=1),
        limit: int = Query(20, ge=1, le=50),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """按用户名搜索当前用户的好友。"""
    users = crud.search_friends(db, current_user.id, q, limit=limit, offset=offset)
    has_more = len(users) > limit
    page_items = users[:limit]

    return {
        "items": [
            {
                "id": user.id,
                "username": user.username,
                "is_online": user.id in chat_manager.active_connections,
                "relationship_status": "friend",
                "friend_request_id": None,
                "can_start_chat": crud.can_start_private_chat(db, current_user.id, user.id),
                "has_conversation": crud.has_private_conversation(db, current_user.id, user.id)
            }
            for user in page_items
        ],
        "has_more": has_more,
        "next_offset": offset + len(page_items) if has_more else None
    }


@router.get("/friends/requests", response_model=FriendRequestListResponse)
async def list_friend_requests(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """返回当前用户的好友请求收件箱和发件箱。"""
    incoming = crud.list_received_friend_requests(db, current_user.id)
    outgoing = crud.list_sent_friend_requests(db, current_user.id)

    return FriendRequestListResponse(
        incoming=[_build_friend_request_summary(db, item, "incoming") for item in incoming],
        outgoing=[_build_friend_request_summary(db, item, "outgoing") for item in outgoing]
    )


@router.post("/friends/requests")
async def send_friend_request(
        payload: FriendRequestCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """发起好友请求。"""
    if payload.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能向自己发送好友请求")

    target_user = crud.get_user(db, payload.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="目标用户不存在")

    if crud.get_friendship(db, current_user.id, payload.user_id):
        raise HTTPException(status_code=400, detail="你们已经是好友")

    if crud.get_pending_friend_request_between(db, current_user.id, payload.user_id):
        raise HTTPException(status_code=400, detail="已有待处理的好友请求")

    try:
        friend_request = crud.create_friend_request(db, current_user.id, payload.user_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="已有待处理的好友请求")

    try:
        await chat_manager.broadcast_friend_access_updated(current_user.id, payload.user_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "friend_access_broadcast_failed", peer_id=payload.user_id, error=str(exc))

    return {"message": "好友请求已发送", "request_id": friend_request.id}


@router.post("/friends/requests/{request_id}/accept")
async def accept_friend_request(
        request_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """接受好友请求。"""
    friend_request = crud.get_friend_request(db, request_id)
    if not friend_request:
        raise HTTPException(status_code=404, detail="好友请求不存在")
    if friend_request.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权处理该好友请求")
    if friend_request.status != "pending":
        raise HTTPException(status_code=400, detail="该好友请求已处理")

    try:
        crud.accept_friend_request_with_chat_access(db, friend_request)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="好友关系已存在")

    try:
        await chat_manager.broadcast_friend_access_updated(current_user.id, friend_request.sender_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "friend_access_broadcast_failed", peer_id=friend_request.sender_id, error=str(exc))

    return {"message": "好友请求已接受"}


@router.post("/friends/requests/{request_id}/reject")
async def reject_friend_request(
        request_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """拒绝好友请求。"""
    friend_request = crud.get_friend_request(db, request_id)
    if not friend_request:
        raise HTTPException(status_code=404, detail="好友请求不存在")
    if friend_request.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权处理该好友请求")
    if friend_request.status != "pending":
        raise HTTPException(status_code=400, detail="该好友请求已处理")

    crud.update_friend_request_status(db, friend_request, "rejected")
    try:
        await chat_manager.broadcast_friend_access_updated(current_user.id, friend_request.sender_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "friend_access_broadcast_failed", peer_id=friend_request.sender_id, error=str(exc))
    return {"message": "好友请求已拒绝"}


@router.delete("/friends/requests/{request_id}")
async def cancel_friend_request(
        request_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """取消自己发出的好友请求。"""
    friend_request = crud.get_friend_request(db, request_id)
    if not friend_request:
        raise HTTPException(status_code=404, detail="好友请求不存在")
    if friend_request.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权取消该好友请求")
    if friend_request.status != "pending":
        raise HTTPException(status_code=400, detail="该好友请求已处理")

    crud.update_friend_request_status(db, friend_request, "cancelled")
    try:
        await chat_manager.broadcast_friend_access_updated(current_user.id, friend_request.receiver_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "friend_access_broadcast_failed", peer_id=friend_request.receiver_id, error=str(exc))
    return {"message": "好友请求已取消"}


@router.delete("/friends/{friend_id}")
async def remove_friend(
        friend_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """删除好友关系。"""
    if not crud.delete_friendship_and_disable_chat(db, current_user.id, friend_id):
        raise HTTPException(status_code=404, detail="好友关系不存在")

    try:
        await chat_manager.broadcast_friend_access_updated(current_user.id, friend_id)
    except Exception as exc:
        log_event(logger, logging.WARNING, "friend_access_broadcast_failed", peer_id=friend_id, error=str(exc))

    return {"message": "好友已删除"}
