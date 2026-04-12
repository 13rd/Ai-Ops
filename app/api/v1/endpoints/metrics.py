from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.container import ContainerSnapshotResponse
from app.schemas.metric import MetricSnapshotResponse
from app.schemas.response import success_response
from app.services.collectors.snapshot_service import ContainerService, MetricService
from app.services.servers.server_service import ServerService

router = APIRouter()


@router.get("/{server_id}/metrics/latest", response_model=dict)
async def get_latest_metrics(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get latest metrics for a server.
    """
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    metrics = await MetricService.get_latest_metrics(db, server_id)

    if not metrics:
        return success_response(
            data=None,
            message="No metrics available for this server",
        )

    return success_response(
        data=MetricSnapshotResponse.model_validate(metrics).model_dump(),
        message="Latest metrics retrieved successfully",
    )


@router.get("/{server_id}/metrics/history", response_model=dict)
async def get_metrics_history(
    server_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get metrics history for a server.
    """
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    metrics = await MetricService.get_metrics_history(db, server_id, limit)

    return success_response(
        data=[MetricSnapshotResponse.model_validate(m).model_dump() for m in metrics],
        message="Metrics history retrieved successfully",
    )


@router.get("/{server_id}/containers", response_model=dict)
async def get_server_containers(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get latest containers for a server.
    """
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    containers = await ContainerService.get_latest_containers(db, server_id)

    return success_response(
        data=[ContainerSnapshotResponse.model_validate(c).model_dump() for c in containers],
        message="Containers retrieved successfully",
    )
