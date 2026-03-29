from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FriendRequestCreate(BaseModel):
    user_id: int


class FriendUserSummary(BaseModel):
    id: int
    username: str


class FriendSummary(FriendUserSummary):
    created_at: datetime


class FriendRequestSummary(BaseModel):
    id: int
    status: str
    created_at: datetime
    responded_at: Optional[datetime] = None
    user: FriendUserSummary


class FriendRequestListResponse(BaseModel):
    incoming: List[FriendRequestSummary]
    outgoing: List[FriendRequestSummary]
