from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.core.deps import get_current_user, require_admin
from app.models.user import UserRole
from app.models.user_server_access import UserServerAccess
from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import ok, paginated
from app.db.base import get_db
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.server import ServerCreate, ServerResponse, ServerUpdate
from app.services.audit.logger import AuditLogger
from app.services.servers.server_service import ServerService

router = APIRouter()

VALID_SORT_FIELDS = {"created_at", "name", "cpu_usage", "memory_usage", "last_seen"}
VALID_SORT_ORDERS = {"asc", "desc"}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_server(
    server_data: ServerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    server = await ServerService.create_server(db, server_data)
    await AuditLogger.log(
        db,
        action=AuditAction.SERVER_CREATED.value,
        user=current_user,
        resource_type="server",
        resource_id=server.id,
        details={"name": server.name, "host": server.host},
        request=request,
    )
    return ok(
        data=ServerResponse.model_validate(server).model_dump(),
        message="Server created successfully",
    )


@router.get("")
async def list_servers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    environment: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="Filter by tag"),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if sort_by not in VALID_SORT_FIELDS:
        raise ValidationError(
            f"Invalid sort field. Valid fields: {sorted(VALID_SORT_FIELDS)}",
            code="invalid_sort_field",
        )
    if sort_order not in VALID_SORT_ORDERS:
        raise ValidationError(
            "Invalid sort order. Use 'asc' or 'desc'.",
            code="invalid_sort_order",
        )

    servers, total = await ServerService.get_servers_with_count(
        db,
        skip=skip,
        limit=limit,
        environment=environment,
        status=status,
        tags=tags,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return paginated(
        items=[ServerResponse.model_validate(s).model_dump() for s in servers],
        limit=limit,
        offset=skip,
        total=total,
        message="Servers retrieved successfully",
    )


@router.get("/{server_id}")
async def get_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise NotFoundError("Server not found")
    return ok(
        data=ServerResponse.model_validate(server).model_dump(),
        message="Server retrieved successfully",
    )


@router.put("/{server_id}")
async def update_server(
    server_id: int,
    server_data: ServerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    server = await ServerService.update_server(db, server_id, server_data)
    if not server:
        raise NotFoundError("Server not found")
    await AuditLogger.log(
        db,
        action=AuditAction.SERVER_UPDATED.value,
        user=current_user,
        resource_type="server",
        resource_id=server.id,
        details=server_data.model_dump(
            exclude_unset=True, exclude={"ssh_password", "ssh_private_key"}
        ),
        request=request,
    )
    return ok(
        data=ServerResponse.model_validate(server).model_dump(),
        message="Server updated successfully",
    )


@router.delete("/{server_id}")
async def delete_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deleted = await ServerService.delete_server(db, server_id)
    if not deleted:
        raise NotFoundError("Server not found")
    await AuditLogger.log(
        db,
        action=AuditAction.SERVER_DELETED.value,
        user=current_user,
        resource_type="server",
        resource_id=server_id,
        request=request,
    )
    return ok(data={"server_id": server_id}, message="Server deleted successfully")


@router.get("/{server_id}/my-access")
async def get_my_server_access(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.ADMIN.value:
        return ok(data={"permission": "write"})
    row = (
        await db.execute(
            select(UserServerAccess).where(
                UserServerAccess.user_id == current_user.id,
                UserServerAccess.server_id == server_id,
            )
        )
    ).scalar_one_or_none()
    return ok(data={"permission": row.permission if row else None})
