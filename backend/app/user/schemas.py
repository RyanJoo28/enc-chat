import re
from typing import Optional

from pydantic import BaseModel, field_validator


class UserBase(BaseModel):
    username: str
    avatar: Optional[str] = None


class UserCreate(UserBase):
    password: str

    @field_validator('password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度不能少于 8 位')
        if not re.search(r"[A-Z]", v):
            raise ValueError('密码必须包含至少一个大写字母')
        if not re.search(r"[a-z]", v):
            raise ValueError('密码必须包含至少一个小写字母')
        if not re.search(r"\d", v):
            raise ValueError('密码必须包含至少一个数字')
        if not re.search(r"[^a-zA-Z0-9]", v):
            raise ValueError('密码必须包含至少一个特殊字符 (如 @, #, $ 等)')
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserChangePassword(BaseModel):
    old_password: str
    new_password: str

    @field_validator('new_password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度不能少于 8 位')
        if not re.search(r"[A-Z]", v):
            raise ValueError('密码必须包含至少一个大写字母')
        if not re.search(r"[a-z]", v):
            raise ValueError('密码必须包含至少一个小写字母')
        if not re.search(r"\d", v):
            raise ValueError('密码必须包含至少一个数字')
        if not re.search(r"[^a-zA-Z0-9]", v):
            raise ValueError('密码必须包含至少一个特殊字符 (如 @, #, $ 等)')
        return v


class UserChangeName(BaseModel):
    new_username: str


class User(UserBase):
    """用户响应模型，不包含密码字段。"""
    id: int

    class Config:
        from_attributes = True
