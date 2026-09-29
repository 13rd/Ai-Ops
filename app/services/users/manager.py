from datetime import datetime
from typing import Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import get_password_hash
from app.models.server import Server
from app.models.user import User
from app.models.user_server_access import UserServerAccess
from app.schemas.user import ServerAccessItem, UserCreate, UserUpdate

class UsersManager:
    @staticmethod
    async def list_users(
        db: AsyncSession, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[User], int]:
        total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        result = await db.execute(
            select(User).order_by(User.id.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), int(total)

    @staticmethod
    async def get_user(db: AsyncSession, user_id: int) -> User:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found")
        return user

    @staticmethod
    async def create_user(db: AsyncSession, data: UserCreate) -> User:
        existing = await db.execute(
            select(User).where((User.email == data.email) | (User.username == data.username))
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("User with this email or username already exists")

        user = User(
            email=data.email,
            username=data.username,
            hashed_password=get_password_hash(data.password),
            role=data.role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def update_user(db: AsyncSession, user_id: int, data: UserUpdate) -> User:
        user = await UsersManager.get_user(db, user_id)

        payload = data.model_dump(exclude_unset=True)
        if "password" in payload:
            user.hashed_password = get_password_hash(payload.pop("password"))

        if "email" in payload or "username" in payload:
            target_email = payload.get("email", user.email)
            target_username = payload.get("username", user.username)
            clash = await db.execute(
                select(User).where(
                    and_(
                        User.id != user_id,
                        (User.email == target_email) | (User.username == target_username),
                    )
                )
            )
            if clash.scalar_one_or_none() is not None:
                raise ConflictError("Email or username already taken by another user")

        for field, value in payload.items():
            setattr(user, field, value)
        user.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def deactivate_user(db: AsyncSession, user_id: int) -> User:
        user = await UsersManager.get_user(db, user_id)
        user.is_active = False
        user.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def set_server_access(
        db: AsyncSession, user_id: int, accesses: list[ServerAccessItem]
    ) -> list[UserServerAccess]:

        await UsersManager.get_user(db, user_id)

        server_ids = [a.server_id for a in accesses]
        if server_ids:
            existing = (
                await db.execute(select(Server.id).where(Server.id.in_(server_ids)))
            ).scalars().all()
            missing = set(server_ids) - set(existing)
            if missing:
                raise NotFoundError(
                    f"Server ids not found: {sorted(missing)}",
                    code="server_not_found",
                )

        await db.execute(delete(UserServerAccess).where(UserServerAccess.user_id == user_id))
        now = datetime.utcnow()
        rows = [
            UserServerAccess(
                user_id=user_id,
                server_id=a.server_id,
                permission=a.permission,
                granted_at=now,
            )
            for a in accesses
        ]
        db.add_all(rows)
        await db.commit()
        return rows

    @staticmethod
    async def get_user_servers(db: AsyncSession, user_id: int) -> list[UserServerAccess]:
        result = await db.execute(
            select(UserServerAccess).where(UserServerAccess.user_id == user_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def has_server_access(
        db: AsyncSession,
        user_id: int,
        server_id: int,
        required: Optional[str] = None,
    ) -> bool:
        result = await db.execute(
            select(UserServerAccess).where(
                and_(
                    UserServerAccess.user_id == user_id,
                    UserServerAccess.server_id == server_id,
                )
            )
        )
        access = result.scalar_one_or_none()
        if access is None:
            return False
        if required == "write":
            return access.permission == "write"
        return True
