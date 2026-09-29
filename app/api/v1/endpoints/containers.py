from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_server_write_access
from app.core.exceptions import AppException, NotFoundError
from app.core.responses import ok
from app.db.base import get_db
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.container import ContainerSnapshotResponse
from app.services.audit.logger import AuditLogger
from app.services.containers.container_control_service import ContainerControlService
from app.services.servers.server_service import ServerService

router = APIRouter()

async def _require_server(db: AsyncSession, server_id: int):
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise NotFoundError("Server not found")
    return server

async def _container_action(
    *,
    db: AsyncSession,
    request: Request,
    user: User,
    server_id: int,
    container_id: str,
    action: str,
    fn,
    error_code: str,
    error_message: str,
    extra_details: dict | None = None,
) -> dict:
    await _require_server(db, server_id)
    success = await fn()
    if not success:
        raise AppException(error_message, code=error_code, status_code=502)
    details = {"server_id": server_id, "container_id": container_id, "action": action}
    if extra_details:
        details.update(extra_details)
    await AuditLogger.log(
        db,
        action=AuditAction.CONTAINER_ACTION.value,
        user=user,
        resource_type="container",
        resource_id=container_id,
        details=details,
        request=request,
    )
    return ok(data=details, message=f"Container {action} succeeded")

@router.post("/servers/{server_id}/containers/{container_id}/start")
async def start_container(
    server_id: int,
    container_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_server_write_access),
):
    return await _container_action(
        db=db,
        request=request,
        user=current_user,
        server_id=server_id,
        container_id=container_id,
        action="start",
        fn=lambda: ContainerControlService.start_container(db, server_id, container_id),
        error_code="container_start_failed",
        error_message="Failed to start container",
    )

@router.post("/servers/{server_id}/containers/{container_id}/stop")
async def stop_container(
    server_id: int,
    container_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_server_write_access),
):
    return await _container_action(
        db=db,
        request=request,
        user=current_user,
        server_id=server_id,
        container_id=container_id,
        action="stop",
        fn=lambda: ContainerControlService.stop_container(db, server_id, container_id),
        error_code="container_stop_failed",
        error_message="Failed to stop container",
    )

@router.post("/servers/{server_id}/containers/{container_id}/restart")
async def restart_container(
    server_id: int,
    container_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_server_write_access),
):
    return await _container_action(
        db=db,
        request=request,
        user=current_user,
        server_id=server_id,
        container_id=container_id,
        action="restart",
        fn=lambda: ContainerControlService.restart_container(db, server_id, container_id),
        error_code="container_restart_failed",
        error_message="Failed to restart container",
    )

@router.delete("/servers/{server_id}/containers/{container_id}")
async def remove_container(
    server_id: int,
    container_id: str,
    request: Request,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_server_write_access),
):
    return await _container_action(
        db=db,
        request=request,
        user=current_user,
        server_id=server_id,
        container_id=container_id,
        action="remove",
        fn=lambda: ContainerControlService.remove_container(db, server_id, container_id, force),
        error_code="container_remove_failed",
        error_message="Failed to remove container",
        extra_details={"force": force},
    )

@router.get("/servers/{server_id}/containers/{container_id}")
async def get_container_details(
    server_id: int,
    container_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_server_write_access),
):
    await _require_server(db, server_id)
    container = await ContainerControlService.get_container_by_id(db, server_id, container_id)
    if not container:
        raise NotFoundError("Container not found")
    return ok(
        data=ContainerSnapshotResponse.model_validate(container).model_dump(),
        message="Container details retrieved successfully",
    )

@router.get("/servers/{server_id}/containers/{container_id}/logs")
async def get_container_logs(
    server_id: int,
    container_id: str,
    tail: int = 100,
    timestamps: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_server_write_access),
):
    await _require_server(db, server_id)
    lines = await ContainerControlService.get_container_logs(
        db, server_id, container_id, tail=tail, timestamps=timestamps
    )
    return ok(data={"lines": lines}, message="Logs retrieved")
