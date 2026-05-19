from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.base import get_db
from app.models.user import User, UserRole
from app.models.user_server_access import ServerPermission, UserServerAccess

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the JWT-authenticated user or raise AuthenticationError."""
    if credentials is None:
        raise AuthenticationError("Missing bearer credentials")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise AuthenticationError("Could not validate credentials")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Token payload missing subject")

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid token subject") from exc

    result = await db.execute(select(User).where(User.id == user_id_int))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise PermissionDeniedError("Inactive user")
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise PermissionDeniedError("Inactive user")
    return current_user


def require_role(required_role: UserRole):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == UserRole.ADMIN:
            return current_user
        if current_user.role != required_role:
            raise PermissionDeniedError(
                f"User does not have required role: {required_role}",
            )
        return current_user

    return role_checker


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise PermissionDeniedError("Admin access required")
    return current_user


async def require_server_write_access(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role == UserRole.ADMIN.value:
        return current_user
    row = (
        await db.execute(
            select(UserServerAccess).where(
                UserServerAccess.user_id == current_user.id,
                UserServerAccess.server_id == server_id,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.permission != ServerPermission.WRITE.value:
        raise PermissionDeniedError("Write access to this server required")
    return current_user
