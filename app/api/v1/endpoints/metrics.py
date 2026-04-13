from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models.historical_metric import AggregationType, MetricType
from app.models.user import User
from app.schemas.container import ContainerSnapshotResponse
from app.schemas.historical_metric import (
    HistoricalMetricsRequest,
    HistoricalMetricsResponse,
    HistoricalMetricResponse,
    MetricsAggregationLevelResponse,
)
from app.schemas.metric import MetricSnapshotResponse
from app.schemas.response import success_response
from app.services.collectors.snapshot_service import ContainerService, MetricService
from app.services.metrics.historical_service import HistoricalMetricService
from app.services.servers.server_service import ServerService

router = APIRouter()
direct_router = APIRouter()  # Separate router for direct access paths


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


# Alternative route for frontend compatibility
@direct_router.get("/metrics/{server_id}/latest", response_model=dict)
async def get_latest_metrics_direct(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get latest metrics for a server.
    Alternative route for frontend compatibility.
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


# Alternative route for frontend compatibility
@direct_router.get("/metrics/{server_id}/history", response_model=dict)
async def get_metrics_history_direct(
    server_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get metrics history for a server.
    Alternative route for frontend compatibility.
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


@router.get("/{server_id}/metrics/historical/{metric_type}", response_model=dict)
async def get_historical_metrics(
    server_id: int,
    metric_type: str,  # This will be validated in the function
    time_range: str = Query(..., description="Time range: 1h, 24h, 7d, 30d"),
    aggregation_level: str = Query("minute", description="Aggregation level: minute, hour, day"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get historical metrics for a server and metric type within a time range.
    """
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    # Validate metric_type
    try:
        validated_metric_type = MetricType(metric_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric type. Valid types: {[e.value for e in MetricType]}",
        )

    # Validate time_range
    from app.services.metrics.historical_service import TimeRange

    try:
        validated_time_range = TimeRange(time_range)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time range. Valid ranges: {[e.value for e in TimeRange]}",
        )

    # Validate aggregation_level
    try:
        validated_aggregation_level = AggregationType(aggregation_level)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid aggregation level. Valid levels: {[e.value for e in AggregationType]}",
        )

    # Get historical metrics
    metrics = await HistoricalMetricService.get_historical_metrics(
        db, server_id, validated_metric_type, validated_time_range, validated_aggregation_level
    )

    return success_response(
        data={
            "server_id": server_id,
            "metric_type": validated_metric_type.value,
            "time_range": validated_time_range.value,
            "aggregation_level": validated_aggregation_level.value,
            "metrics": [HistoricalMetricResponse.model_validate(m).model_dump() for m in metrics],
        },
        message="Historical metrics retrieved successfully",
    )


# Alternative route to support direct /metrics access (for frontend compatibility)
@direct_router.get("/metrics/{server_id}/historical/{metric_type}", response_model=dict)
async def get_historical_metrics_direct(
    server_id: int,
    metric_type: str,  # This will be validated in the function
    time_range: str = Query(..., description="Time range: 1h, 24h, 7d, 30d"),
    aggregation_level: str = Query("minute", description="Aggregation level: minute, hour, day"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get historical metrics for a server and metric type within a time range.
    Alternative route for frontend compatibility.
    """
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    # Validate metric_type
    try:
        validated_metric_type = MetricType(metric_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric type. Valid types: {[e.value for e in MetricType]}",
        )

    # Validate time_range
    from app.services.metrics.historical_service import TimeRange

    try:
        validated_time_range = TimeRange(time_range)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time range. Valid ranges: {[e.value for e in TimeRange]}",
        )

    # Validate aggregation_level
    try:
        validated_aggregation_level = AggregationType(aggregation_level)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid aggregation level. Valid levels: {[e.value for e in AggregationType]}",
        )

    # Get historical metrics
    metrics = await HistoricalMetricService.get_historical_metrics(
        db, server_id, validated_metric_type, validated_time_range, validated_aggregation_level
    )

    return success_response(
        data={
            "server_id": server_id,
            "metric_type": validated_metric_type.value,
            "time_range": validated_time_range.value,
            "aggregation_level": validated_aggregation_level.value,
            "metrics": [HistoricalMetricResponse.model_validate(m).model_dump() for m in metrics],
        },
        message="Historical metrics retrieved successfully",
    )


@router.get("/{server_id}/metrics/available-aggregations", response_model=dict)
async def get_available_aggregation_levels(
    server_id: int,
    metric_type: str = Query(..., description="Metric type to check"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get available aggregation levels for a specific metric type on a server.
    """
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    # Validate metric_type
    try:
        validated_metric_type = MetricType(metric_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric type. Valid types: {[e.value for e in MetricType]}",
        )

    # Get available aggregation levels
    levels = await HistoricalMetricService.get_available_aggregation_levels(
        db, server_id, validated_metric_type
    )

    return success_response(
        data={
            "metric_type": validated_metric_type.value,
            "available_levels": [level.value for level in levels],
        },
        message="Available aggregation levels retrieved successfully",
    )


# Alternative route for frontend compatibility
@direct_router.get("/metrics/{server_id}/available-aggregations", response_model=dict)
async def get_available_aggregation_levels_direct(
    server_id: int,
    metric_type: str = Query(..., description="Metric type to check"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get available aggregation levels for a specific metric type on a server.
    Alternative route for frontend compatibility.
    """
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )

    # Validate metric_type
    try:
        validated_metric_type = MetricType(metric_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric type. Valid types: {[e.value for e in MetricType]}",
        )

    # Get available aggregation levels
    levels = await HistoricalMetricService.get_available_aggregation_levels(
        db, server_id, validated_metric_type
    )

    return success_response(
        data={
            "metric_type": validated_metric_type.value,
            "available_levels": [level.value for level in levels],
        },
        message="Available aggregation levels retrieved successfully",
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


# Alternative route for frontend compatibility
@direct_router.get("/containers/{server_id}", response_model=dict)
async def get_server_containers_direct(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get latest containers for a server.
    Alternative route for frontend compatibility.
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
