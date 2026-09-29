from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.responses import ok
from app.core.security import decode_refresh_token
from app.db.base import get_db
from app.models.audit_log import AuditAction
from app.schemas.user import LoginRequest, UserResponse
from app.services.audit.logger import AuditLogger
from app.services.auth.auth_service import AuthService

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,
    )

def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)

@router.post("/login")
async def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await AuthService.authenticate_user(db, login_data.username, login_data.password)
    if not user:
        await AuditLogger.log(
            db,
            action=AuditAction.LOGIN_FAILED.value,
            details={"username": login_data.username},
            request=request,
        )
        raise AuthenticationError("Incorrect username or password")
    if not user.is_active:
        await AuditLogger.log(
            db,
            action=AuditAction.LOGIN_FAILED.value,
            user=user,
            details={"reason": "inactive"},
            request=request,
        )
        raise PermissionDeniedError("User is inactive")

    access_token, refresh_token, _ = await AuthService.issue_token_pair(db, user)
    _set_refresh_cookie(response, refresh_token)

    await AuditLogger.log(
        db,
        action=AuditAction.LOGIN.value,
        user=user,
        request=request,
    )

    return ok(
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user).model_dump(),
        },
        message="Login successful",
    )

@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise AuthenticationError("Missing refresh token")

    payload = decode_refresh_token(refresh_token)
    if payload is None:
        _clear_refresh_cookie(response)
        raise AuthenticationError("Invalid or expired refresh token")

    jti = payload.get("jti")
    sub = payload.get("sub")
    if not jti or not sub:
        _clear_refresh_cookie(response)
        raise AuthenticationError("Malformed refresh token")

    record = await AuthService.get_active_refresh_token(db, jti)
    if record is None:
        _clear_refresh_cookie(response)
        raise AuthenticationError("Refresh token revoked or expired")

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        _clear_refresh_cookie(response)
        raise AuthenticationError("Invalid token subject") from exc

    user = await AuthService.get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        _clear_refresh_cookie(response)
        raise AuthenticationError("User not found or inactive")

    await AuthService.revoke_refresh_token(db, jti)
    access_token, new_refresh, _ = await AuthService.issue_token_pair(db, user)
    _set_refresh_cookie(response, new_refresh)

    await AuditLogger.log(
        db,
        action=AuditAction.TOKEN_REFRESHED.value,
        user=user,
        request=request,
    )

    return ok(
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user).model_dump(),
        },
        message="Token refreshed",
    )

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    user = None
    if refresh_token:
        payload = decode_refresh_token(refresh_token)
        if payload:
            jti = payload.get("jti")
            if jti:
                record = await AuthService.get_active_refresh_token(db, jti)
                if record is not None:
                    user = await AuthService.get_user_by_id(db, record.user_id)
                    await AuthService.revoke_refresh_token(db, jti)

    _clear_refresh_cookie(response)

    await AuditLogger.log(
        db,
        action=AuditAction.LOGOUT.value,
        user=user,
        request=request,
    )

    return ok(message="Logout successful")

@router.get("/me")
async def get_current_user_info(current_user=Depends(get_current_user)):
    return ok(
        data=UserResponse.model_validate(current_user).model_dump(),
        message="User retrieved successfully",
    )
