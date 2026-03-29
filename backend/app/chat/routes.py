from datetime import datetime
import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import crud
from ..database import get_db
from ..database.models import User, Group, GroupMember
from ..e2ee.service import rotate_group_sender_key_epoch
from ..settings import GROUP_AVATAR_DIR
from ..user.dependencies import get_current_user
from ..utils import encryption
from ..utils.file_validation import validate_file_payload
from ..utils.limiter import get_auth_or_remote_address, limiter
from .manager import manager

router = APIRouter()

GROUP_AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_GROUP_AVATAR_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}
MAX_GROUP_AVATAR_SIZE = 5 * 1024 * 1024


# 请求模型
class GroupCreate(BaseModel):
    name: str
    members: List[int]


class GroupUpdate(BaseModel):
    name: str


@router.post("/group/create")
async def create_new_group(
        group: GroupCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """创建群聊。"""
    friend_ids = crud.get_friend_ids(db, current_user.id)
    invalid_user_ids = [user_id for user_id in group.members if user_id not in friend_ids]
    if invalid_user_ids:
        raise HTTPException(status_code=400, detail="只能邀请好友建群")

    new_group = crud.create_group(db, group.name, current_user.id, group.members)
    all_members = group.members + [current_user.id]
    epoch = rotate_group_sender_key_epoch(db, new_group.id, current_user.id)
    await manager.broadcast_group_created(new_group.id, new_group.name, all_members)
    await manager.broadcast_group_epoch_changed(all_members, new_group.id, epoch.epoch)
    return {"message": "群组创建成功", "group_id": new_group.id}


@router.get("/group/search")
@limiter.limit("900/minute", key_func=get_auth_or_remote_address)
def search_groups(
        request: Request,
        q: str = Query(..., min_length=1),
        limit: int = Query(20, ge=1, le=50),
        offset: int = Query(0, ge=0),
        anchor_ts: int | None = Query(None, ge=0),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """按群组名称搜索群组。"""
    effective_anchor_ts = anchor_ts or int(datetime.now().timestamp())
    anchor_time = datetime.fromtimestamp(effective_anchor_ts)
    groups = crud.search_groups(db, q, limit=limit, offset=offset, anchor_time=anchor_time)
    my_group_ids = set(group_id for group_id, in db.query(GroupMember.group_id).filter(GroupMember.user_id == current_user.id).all())
    access_state_map = crud.get_group_access_state_map(db, current_user.id, [group.id for group, _ in groups[:limit]])

    has_more = len(groups) > limit
    page_items = groups[:limit]

    results = []
    for group, last_activity_at in page_items:
        member_count = db.query(GroupMember).filter(GroupMember.group_id == group.id).count()
        results.append({
            "id": group.id,
            "name": group.name,
            "avatar": group.avatar,
            "is_member": group.id in my_group_ids,
            "member_count": member_count,
            "last_activity_ts": int(last_activity_at.timestamp()) if last_activity_at else None,
            **access_state_map.get(group.id, {
                "invite_status": None,
                "invite_id": None,
                "join_request_status": None,
                "join_request_id": None,
            })
        })

    return {
        "items": results,
        "has_more": has_more,
        "next_offset": offset + len(results) if has_more else None,
        "anchor_ts": effective_anchor_ts
    }


@router.put("/group/{group_id}")
async def update_group(
        group_id: int,
        data: GroupUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """修改群组名称。"""
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以修改群名")

    crud.update_group_name(db, group_id, data.name)

    members = crud.get_group_members(db, group_id)
    await manager.broadcast_group_created(group.id, data.name, members)

    return {"message": "群名已更新", "name": data.name}


@router.post("/group/{group_id}/avatar")
async def upload_group_avatar(
        group_id: int,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """上传并设置群组头像，仅群主可用。"""
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以修改群头像")

    file.file.seek(0, 2)
    file_size = file.file.tell()
    await file.seek(0)
    if file_size > MAX_GROUP_AVATAR_SIZE:
        raise HTTPException(status_code=413, detail="文件过大")

    content = await file.read()

    try:
        file_ext = validate_file_payload(file.filename, file.content_type, content, ALLOWED_GROUP_AVATAR_EXTENSIONS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    random_name = f"{uuid.uuid4().hex}{file_ext}"
    file_path = GROUP_AVATAR_DIR / random_name
    encrypted_content = encryption.encrypt_file_content(content)

    try:
        with file_path.open("wb") as f:
            f.write(encrypted_content)

        updated_group = crud.update_group_avatar(db, group_id, random_name)
    except Exception:
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        raise HTTPException(status_code=500, detail="群头像上传失败")

    member_ids = crud.get_group_members(db, group_id)
    await manager.broadcast_group_created(updated_group.id, updated_group.name, member_ids)

    return {"message": "群头像上传成功", "avatar": random_name}


@router.get("/group/avatar/{filename}")
async def get_group_avatar(filename: str):
    """获取公开访问的群组头像。"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    file_path = GROUP_AVATAR_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    with file_path.open("rb") as f:
        stored_data = f.read()

    if stored_data.startswith(encryption.FILE_ENCRYPTION_MAGIC):
        avatar_bytes = encryption.decrypt_file_content(stored_data)
        if not avatar_bytes and stored_data:
            raise HTTPException(status_code=500, detail="群头像解密失败")
    else:
        avatar_bytes = stored_data
        try:
            with file_path.open("wb") as f:
                f.write(encryption.encrypt_file_content(stored_data))
        except OSError:
            pass

    media_type = "application/octet-stream"
    lower_name = filename.lower()
    if lower_name.endswith(('.jpg', '.jpeg')):
        media_type = "image/jpeg"
    elif lower_name.endswith('.png'):
        media_type = "image/png"
    elif lower_name.endswith('.gif'):
        media_type = "image/gif"

    return Response(content=avatar_bytes, media_type=media_type)


@router.delete("/group/{group_id}")
async def disband_group(
        group_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """解散群组。"""
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    # 严格权限：只有群主可以解散
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以解散群组")

    members = crud.get_group_members(db, group_id)

    crud.delete_group(db, group_id)

    await manager.broadcast_group_created(group_id, "Deleted", members)

    return {"message": "群组已解散"}


@router.get("/group/{group_id}/members")
def get_group_members(
        group_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """获取群成员列表及群主 ID。"""
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    member_ids = crud.get_group_members(db, group_id)
    if current_user.id not in member_ids:
        raise HTTPException(status_code=403, detail="无权查看该群组")

    users = crud.get_group_members_detailed(db, group_id)

    result = []
    for u in users:
        role = "owner" if u.id == group.owner_id else "member"
        result.append({
            "id": u.id,
            "username": u.username,
            "avatar": u.avatar,
            "role": role
        })

    return {
        "owner_id": group.owner_id,
        "name": group.name,
        "avatar": group.avatar,
        "members": result
    }


@router.delete("/group/{group_id}/member/{user_id}")
async def remove_member(
        group_id: int,
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """移除成员，仅群主可用。"""
    group = crud.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")

    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有群主可以移除成员")

    if user_id == group.owner_id:
        raise HTTPException(status_code=400, detail="群主不能移除自己")

    crud.remove_group_member(db, group_id, user_id)

    remaining_members = crud.get_group_members(db, group_id)
    epoch = rotate_group_sender_key_epoch(db, group.id, current_user.id)
    await manager.broadcast_group_created(group.id, group.name, remaining_members + [user_id])
    await manager.broadcast_group_epoch_changed(remaining_members + [user_id], group.id, epoch.epoch)

    return {"message": "成员已移除"}
