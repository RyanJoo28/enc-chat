import datetime
import os
from typing import Optional

import jwt
from dotenv import load_dotenv
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..database import crud
from ..database.models import User

# 环境变量
load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

if not SECRET_KEY:
    raise ValueError("严重错误: 未设置 JWT_SECRET_KEY 环境变量！")

# 密码哈希
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class UserManager:
    """用户业务逻辑管理器。"""

    def hash_password(self, password: str) -> str:
        """使用 Argon2id 生成密码哈希。"""
        return pwd_context.hash(password)

    def verify_password(self, plain_pwd: str, hashed: str) -> bool:
        """验证明文密码与哈希值是否匹配。"""
        return pwd_context.verify(plain_pwd, hashed)

    async def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        return crud.get_user_by_username(db, username)

    async def create_user(self, db: Session, username: str, password: str) -> User:
        db_user = User(username=username, password=password)
        db.add(db_user)
        db.flush()
        crud.sync_user_search_tokens(db, db_user.id, username)
        db.commit()
        db.refresh(db_user)
        return db_user

    def generate_token(self, user: User) -> str:
        """为用户生成访问令牌。"""
        payload = {
            "sub": user.username,
            "user_id": user.id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    async def update_password(self, db: Session, user: User, new_password: str):
        """更新用户密码。"""
        hashed_pwd = self.hash_password(new_password)
        user.password = hashed_pwd
        db.commit()
        db.refresh(user)
        return user

    async def update_username(self, db: Session, user: User, new_username: str):
        """更新用户名并检查重名。"""
        existing = crud.get_user_by_username(db, new_username)
        if existing:
            return False

        user.username = new_username
        crud.sync_user_search_tokens(db, user.id, new_username)
        db.commit()
        db.refresh(user)
        return True
