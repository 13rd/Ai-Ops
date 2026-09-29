from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import UserCreate

class AuthService:

    @staticmethod
    async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:

        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return user

    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate) -> User:

        hashed_password = get_password_hash(user_data.password)

        user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            role=user_data.role,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def issue_token_pair(
        db: AsyncSession, user: User
    ) -> tuple[str, str, datetime]:

        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh_token, jti, refresh_expires_at = create_refresh_token(user_id=user.id)

        db.add(
            RefreshToken(
                jti=jti,
                user_id=user.id,
                expires_at=refresh_expires_at,
            )
        )
        await db.commit()

        return access_token, refresh_token, refresh_expires_at

    @staticmethod
    async def get_active_refresh_token(
        db: AsyncSession, jti: str
    ) -> Optional[RefreshToken]:

        result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        record = result.scalar_one_or_none()
        if record is None:
            return None
        if record.revoked:
            return None
        if record.expires_at < datetime.utcnow():
            return None
        return record

    @staticmethod
    async def revoke_refresh_token(db: AsyncSession, jti: str) -> bool:

        result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        record = result.scalar_one_or_none()
        if record is None or record.revoked:
            return False
        record.revoked = True
        record.revoked_at = datetime.utcnow()
        await db.commit()
        return True
