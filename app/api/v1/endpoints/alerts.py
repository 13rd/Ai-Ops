from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import ok
from app.db.base import get_db
from app.models.alert import AlertSeverity, AlertStatus
from app.models.user import User
from app.schemas.alert import AlertResponse
from app.services.alerts.alert_service import AlertService

router = APIRouter()

def _parse_status(raw: str | None) -> AlertStatus | None:
    if raw is None:
        return None
    try:
        return AlertStatus(raw.lower())
    except ValueError as exc:
        raise ValidationError(
            f"Invalid status. Valid values: {[e.value for e in AlertStatus]}",
            code="invalid_status",
        ) from exc

def _parse_severity(raw: str | None) -> AlertSeverity | None:
    if raw is None:
        return None
    try:
        return AlertSeverity(raw.lower())
    except ValueError as exc:
        raise ValidationError(
            f"Invalid severity. Valid values: {[e.value for e in AlertSeverity]}",
            code="invalid_severity",
        ) from exc

@router.get("/")
async def list_alerts(
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
    server_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    status_enum = _parse_status(status_filter)
    severity_enum = _parse_severity(severity)

    alerts = await AlertService.get_alerts(db, status_enum, severity_enum, server_id, limit, offset)
    return ok(
        data={
            "alerts": [AlertResponse.model_validate(a).model_dump() for a in alerts],
            "pagination": {"limit": limit, "offset": offset},
        },
        message="Alerts retrieved successfully",
    )

@router.get("/{alert_id}")
async def get_alert_detail(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = await AlertService.get_alert_by_id(db, alert_id)
    if not alert:
        raise NotFoundError("Alert not found")
    return ok(
        data=AlertResponse.model_validate(alert).model_dump(),
        message="Alert details retrieved successfully",
    )

@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = await AlertService.acknowledge_alert(db, alert_id, current_user.id)
    if not success:
        raise ValidationError(
            "Could not acknowledge alert. It may not exist or already be resolved.",
            code="alert_not_acknowledgeable",
        )
    alert = await AlertService.get_alert_by_id(db, alert_id)
    return ok(
        data=AlertResponse.model_validate(alert).model_dump(),
        message="Alert acknowledged successfully",
    )

@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = await AlertService.resolve_alert(db, alert_id)
    if not success:
        raise ValidationError(
            "Could not resolve alert. It may not exist or already be resolved.",
            code="alert_not_resolvable",
        )
    alert = await AlertService.get_alert_by_id(db, alert_id)
    return ok(
        data=AlertResponse.model_validate(alert).model_dump(),
        message="Alert resolved successfully",
    )

@router.get("/count")
async def get_alerts_count(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    server_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    status_enum = _parse_status(status)
    severity_enum = _parse_severity(severity)
    count = await AlertService.get_alerts_count(db, status_enum, severity_enum, server_id)
    return ok(
        data={
            "count": count,
            "filters": {"status": status, "severity": severity, "server_id": server_id},
        },
        message="Alert count retrieved successfully",
    )
