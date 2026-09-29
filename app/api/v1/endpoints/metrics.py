from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import assert_server_read_access, get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import ok
from app.db.base import get_db
from app.models.historical_metric import AggregationType, MetricType
from app.models.user import User
from app.schemas.container import ContainerSnapshotResponse
from app.schemas.historical_metric import HistoricalMetricResponse
from app.schemas.metric import MetricSnapshotResponse
from app.services.collectors.snapshot_service import ContainerService, MetricService
from app.services.metrics.historical_service import HistoricalMetricService, TimeRange
from app.services.servers.server_service import ServerService

router = APIRouter()
direct_router = APIRouter()

async def _require_server(db: AsyncSession, server_id: int, user: User):
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise NotFoundError("Server not found")
    await assert_server_read_access(db, user, server_id)
    return server

def _parse_metric_type(metric_type: str) -> MetricType:
    try:
        return MetricType(metric_type)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid metric type. Valid types: {[e.value for e in MetricType]}",
            code="invalid_metric_type",
        ) from exc

def _parse_time_range(time_range: str) -> TimeRange:
    try:
        return TimeRange(time_range)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid time range. Valid ranges: {[e.value for e in TimeRange]}",
            code="invalid_time_range",
        ) from exc

def _parse_aggregation(level: str) -> AggregationType:
    try:
        return AggregationType(level)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid aggregation level. Valid levels: {[e.value for e in AggregationType]}",
            code="invalid_aggregation_level",
        ) from exc

async def _latest_metrics(db: AsyncSession, server_id: int, user: User):
    await _require_server(db, server_id, user)
    metrics = await MetricService.get_latest_metrics(db, server_id)
    if not metrics:
        return ok(data=None, message="No metrics available for this server")
    return ok(
        data=MetricSnapshotResponse.model_validate(metrics).model_dump(),
        message="Latest metrics retrieved successfully",
    )

async def _metrics_history(db: AsyncSession, server_id: int, limit: int, user: User):
    await _require_server(db, server_id, user)
    metrics = await MetricService.get_metrics_history(db, server_id, limit)
    return ok(
        data=[MetricSnapshotResponse.model_validate(m).model_dump() for m in metrics],
        message="Metrics history retrieved successfully",
    )

async def _historical(
    db: AsyncSession,
    server_id: int,
    metric_type: str,
    time_range: str,
    aggregation_level: str,
    user: User,
):
    await _require_server(db, server_id, user)
    parsed_metric_type = _parse_metric_type(metric_type)
    parsed_range = _parse_time_range(time_range)
    parsed_agg = _parse_aggregation(aggregation_level)

    metrics = await HistoricalMetricService.get_historical_metrics(
        db, server_id, parsed_metric_type, parsed_range, parsed_agg
    )
    return ok(
        data={
            "server_id": server_id,
            "metric_type": parsed_metric_type.value,
            "time_range": parsed_range.value,
            "aggregation_level": parsed_agg.value,
            "metrics": [HistoricalMetricResponse.model_validate(m).model_dump() for m in metrics],
        },
        message="Historical metrics retrieved successfully",
    )

async def _available_aggregations(db: AsyncSession, server_id: int, metric_type: str, user: User):
    await _require_server(db, server_id, user)
    parsed_metric_type = _parse_metric_type(metric_type)
    levels = await HistoricalMetricService.get_available_aggregation_levels(
        db, server_id, parsed_metric_type
    )
    return ok(
        data={
            "metric_type": parsed_metric_type.value,
            "available_levels": [level.value for level in levels],
        },
        message="Available aggregation levels retrieved successfully",
    )

async def _server_containers(db: AsyncSession, server_id: int, user: User):
    await _require_server(db, server_id, user)
    containers = await ContainerService.get_latest_containers(db, server_id)
    return ok(
        data=[ContainerSnapshotResponse.model_validate(c).model_dump() for c in containers],
        message="Containers retrieved successfully",
    )

@router.get("/{server_id}/metrics/latest")
async def get_latest_metrics(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _latest_metrics(db, server_id, current_user)

@direct_router.get("/metrics/{server_id}/latest")
async def get_latest_metrics_direct(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _latest_metrics(db, server_id, current_user)

@router.get("/{server_id}/metrics/history")
async def get_metrics_history(
    server_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _metrics_history(db, server_id, limit, current_user)

@direct_router.get("/metrics/{server_id}/history")
async def get_metrics_history_direct(
    server_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _metrics_history(db, server_id, limit, current_user)

@router.get("/{server_id}/metrics/historical/{metric_type}")
async def get_historical_metrics(
    server_id: int,
    metric_type: str,
    time_range: str = Query(..., description="Time range: 1h, 24h, 7d, 30d"),
    aggregation_level: str = Query("minute"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _historical(
        db, server_id, metric_type, time_range, aggregation_level, current_user
    )

@direct_router.get("/metrics/{server_id}/historical/{metric_type}")
async def get_historical_metrics_direct(
    server_id: int,
    metric_type: str,
    time_range: str = Query(..., description="Time range: 1h, 24h, 7d, 30d"),
    aggregation_level: str = Query("minute"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _historical(
        db, server_id, metric_type, time_range, aggregation_level, current_user
    )

@router.get("/{server_id}/metrics/available-aggregations")
async def get_available_aggregation_levels(
    server_id: int,
    metric_type: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _available_aggregations(db, server_id, metric_type, current_user)

@direct_router.get("/metrics/{server_id}/available-aggregations")
async def get_available_aggregation_levels_direct(
    server_id: int,
    metric_type: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _available_aggregations(db, server_id, metric_type, current_user)

@router.get("/{server_id}/containers")
async def get_server_containers(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _server_containers(db, server_id, current_user)

@direct_router.get("/containers/{server_id}")
async def get_server_containers_direct(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _server_containers(db, server_id, current_user)
