from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.core.responses import ok, paginated
from app.db.base import get_db
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.server import ServerResponse
from app.schemas.user import (
    ServerAccessAssignRequest,
    ServerAccessResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.audit.logger import AuditLogger
from app.services.servers.server_service import ServerService
from app.services.users.manager import UsersManager

router = APIRouter()

@router.get("")
async def list_users(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    users, total = await UsersManager.list_users(db, limit=limit, offset=offset)
    return paginated(
        items=[UserResponse.model_validate(u).model_dump() for u in users],
        limit=limit,
        offset=offset,
        total=total,
        message="Users retrieved successfully",
    )

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await UsersManager.create_user(db, user_data)
    await AuditLogger.log(
        db,
        action=AuditAction.USER_CREATED.value,
        user=current_user,
        resource_type="user",
        resource_id=user.id,
        details={"role": user.role, "username": user.username},
        request=request,
    )
    return ok(
        data=UserResponse.model_validate(user).model_dump(),
        message="User created successfully",
    )

@router.get("/me/servers")
async def list_my_servers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role == "admin":
        servers = await ServerService.get_servers(db, limit=1000)
        return ok(
            data=[ServerResponse.model_validate(s).model_dump() for s in servers],
            message="Accessible servers retrieved",
        )

    accesses = await UsersManager.get_user_servers(db, current_user.id)
    server_ids = [a.server_id for a in accesses]
    servers = []
    for sid in server_ids:
        s = await ServerService.get_server_by_id(db, sid)
        if s is not None:
            servers.append(s)
    return ok(
        data=[ServerResponse.model_validate(s).model_dump() for s in servers],
        message="Accessible servers retrieved",
    )

@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await UsersManager.get_user(db, user_id)
    return ok(
        data=UserResponse.model_validate(user).model_dump(),
        message="User retrieved successfully",
    )

@router.put("/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await UsersManager.update_user(db, user_id, user_data)
    await AuditLogger.log(
        db,
        action=AuditAction.USER_UPDATED.value,
        user=current_user,
        resource_type="user",
        resource_id=user.id,
        details=user_data.model_dump(exclude_unset=True, exclude={"password"}),
        request=request,
    )
    return ok(
        data=UserResponse.model_validate(user).model_dump(),
        message="User updated successfully",
    )

@router.delete("/{user_id}")
async def deactivate_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await UsersManager.deactivate_user(db, user_id)
    await AuditLogger.log(
        db,
        action=AuditAction.USER_DEACTIVATED.value,
        user=current_user,
        resource_type="user",
        resource_id=user.id,
        request=request,
    )
    return ok(
        data=UserResponse.model_validate(user).model_dump(),
        message="User deactivated successfully",
    )

@router.put("/{user_id}/servers")
async def assign_user_servers(
    user_id: int,
    payload: ServerAccessAssignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rows = await UsersManager.set_server_access(db, user_id, payload.accesses)
    await AuditLogger.log(
        db,
        action=AuditAction.SERVER_ACCESS_ASSIGNED.value,
        user=current_user,
        resource_type="user",
        resource_id=user_id,
        details={"accesses": [a.model_dump() for a in payload.accesses]},
        request=request,
    )
    return ok(
        data=[ServerAccessResponse.model_validate(r).model_dump() for r in rows],
        message="User server access updated successfully",
    )

@router.get("/{user_id}/servers")
async def get_user_servers(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    await UsersManager.get_user(db, user_id)
    rows = await UsersManager.get_user_servers(db, user_id)
    return ok(
        data=[ServerAccessResponse.model_validate(r).model_dump() for r in rows],
        message="User server access retrieved successfully",
    )
