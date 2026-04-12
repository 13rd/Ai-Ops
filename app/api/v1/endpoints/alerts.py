from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.alert import AlertFilterRequest, AlertResponse
from app.schemas.response import success_response
from app.services.alerts.alert_service import AlertService
from app.models.alert import AlertStatus, AlertSeverity

router = APIRouter()


@router.get("/", response_model=dict)
async def list_alerts(
    status_filter: str = Query(
        None, alias="status", description="Filter by status: open, acknowledged, resolved"
    ),
    severity: str = Query(None, description="Filter by severity: low, medium, high, critical"),
    server_id: int = Query(None, description="Filter by server ID"),
    limit: int = Query(100, ge=1, le=1000, description="Number of alerts to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List alerts with optional filters.
    """
    # Parse status filter
    status_enum = None
    if status_filter:
        try:
            status_enum = AlertStatus(status_filter.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Valid values: {[e.value for e in AlertStatus]}",
            )

    # Parse severity filter
    severity_enum = None
    if severity:
        try:
            severity_enum = AlertSeverity(severity.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity. Valid values: {[e.value for e in AlertSeverity]}",
            )

    alerts = await AlertService.get_alerts(db, status_enum, severity_enum, server_id, limit, offset)

    return success_response(
        data={
            "alerts": [AlertResponse.model_validate(alert).model_dump() for alert in alerts],
            "pagination": {"limit": limit, "offset": offset},
        },
        message="Alerts retrieved successfully",
    )


@router.get("/{alert_id}", response_model=dict)
async def get_alert_detail(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a specific alert.
    """
    alert = await AlertService.get_alert_by_id(db, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    return success_response(
        data=AlertResponse.model_validate(alert).model_dump(),
        message="Alert details retrieved successfully",
    )


@router.post("/{alert_id}/acknowledge", response_model=dict)
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Acknowledge an alert.
    """
    success = await AlertService.acknowledge_alert(db, alert_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not acknowledge alert. It may not exist or already be resolved.",
        )

    # Get the updated alert to return
    alert = await AlertService.get_alert_by_id(db, alert_id)

    return success_response(
        data=AlertResponse.model_validate(alert).model_dump(),
        message="Alert acknowledged successfully",
    )


@router.post("/{alert_id}/resolve", response_model=dict)
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resolve an alert (mark as fixed).
    """
    success = await AlertService.resolve_alert(db, alert_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve alert. It may not exist or already be resolved.",
        )

    # Get the updated alert to return
    alert = await AlertService.get_alert_by_id(db, alert_id)

    return success_response(
        data=AlertResponse.model_validate(alert).model_dump(), message="Alert resolved successfully"
    )


@router.get("/count", response_model=dict)
async def get_alerts_count(
    status: str = Query(None, description="Filter by status: open, acknowledged, resolved"),
    severity: str = Query(None, description="Filter by severity: low, medium, high, critical"),
    server_id: int = Query(None, description="Filter by server ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get count of alerts with optional filters.
    """
    # Parse status filter
    status_enum = None
    if status:
        try:
            status_enum = AlertStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Valid values: {[e.value for e in AlertStatus]}",
            )

    # Parse severity filter
    severity_enum = None
    if severity:
        try:
            severity_enum = AlertSeverity(severity.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity. Valid values: {[e.value for e in AlertSeverity]}",
            )

    count = await AlertService.get_alerts_count(db, status_enum, severity_enum, server_id)

    return success_response(
        data={
            "count": count,
            "filters": {"status": status, "severity": severity, "server_id": server_id},
        },
        message="Alert count retrieved successfully",
    )
