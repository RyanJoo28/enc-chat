from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class GroupInviteCreate(BaseModel):
    user_id: int


class GroupJoinRequestCreate(BaseModel):
    note: Optional[str] = Field(default=None, max_length=255)


class ChatUserSummary(BaseModel):
    id: int
    username: str
    avatar: Optional[str] = None


class GroupInviteSummary(BaseModel):
    id: int
    group_id: int
    group_name: str
    group_avatar: Optional[str] = None
    status: str
    created_at: datetime
    responded_at: Optional[datetime] = None
    inviter: ChatUserSummary
    invitee: ChatUserSummary


class GroupInviteListResponse(BaseModel):
    items: List[GroupInviteSummary]


class GroupJoinRequestSummary(BaseModel):
    id: int
    group_id: int
    group_name: str
    group_avatar: Optional[str] = None
    status: str
    note: Optional[str] = None
    created_at: datetime
    responded_at: Optional[datetime] = None
    requester: ChatUserSummary


class GroupJoinRequestListResponse(BaseModel):
    items: List[GroupJoinRequestSummary]
