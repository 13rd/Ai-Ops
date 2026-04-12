from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.base import get_db
from app.schemas.response import error_response, success_response
from app.schemas.user import LoginRequest, Token, UserResponse
from app.services.auth.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=dict)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Login endpoint. Returns JWT access token.
    """
    user = await AuthService.authenticate_user(db, login_data.username, login_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    return success_response(
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user).model_dump(),
        },
        message="Login successful",
    )


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user=Depends(get_current_user),
):
    """
    Get current authenticated user information.
    """
    return success_response(
        data=UserResponse.model_validate(current_user).model_dump(),
        message="User retrieved successfully",
    )
