from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    assert_server_read_access,
    get_accessible_server_ids,
    get_current_user,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import ok, paginated
from app.db.base import get_db
from app.models.anomaly import Anomaly, AnomalyStatus
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.anomaly import (
    ANOMALY_SEVERITIES,
    ANOMALY_STATUSES,
    ANOMALY_TYPES,
    AnomalyResponse,
    AnomalyStatusUpdate,
)
from app.services.audit.logger import AuditLogger

router = APIRouter()
direct_router = APIRouter()

def _build_filters(
    server_id: Optional[int],
    anomaly_type: Optional[str],
    severity: Optional[str],
    status: Optional[str],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    allowed_server_ids: Optional[set[int]] = None,
):
    if anomaly_type is not None and anomaly_type not in ANOMALY_TYPES:
        raise ValidationError(
            f"Invalid anomaly_type. Valid: {sorted(ANOMALY_TYPES)}", code="invalid_anomaly_type"
        )
    if severity is not None and severity not in ANOMALY_SEVERITIES:
        raise ValidationError(
            f"Invalid severity. Valid: {sorted(ANOMALY_SEVERITIES)}", code="invalid_severity"
        )
    if status is not None and status not in ANOMALY_STATUSES:
        raise ValidationError(
            f"Invalid status. Valid: {sorted(ANOMALY_STATUSES)}", code="invalid_status"
        )

    conds = []
    if allowed_server_ids is not None:
        conds.append(Anomaly.server_id.in_(allowed_server_ids))
    if server_id is not None:
        conds.append(Anomaly.server_id == server_id)
    if anomaly_type is not None:
        conds.append(Anomaly.anomaly_type == anomaly_type)
    if severity is not None:
        conds.append(Anomaly.severity == severity)
    if status is not None:
        conds.append(Anomaly.status == status)
    if date_from is not None:
        conds.append(Anomaly.detected_at >= date_from)
    if date_to is not None:
        conds.append(Anomaly.detected_at <= date_to)
    return conds

async def _query_anomalies(
    db: AsyncSession,
    *,
    server_id: Optional[int] = None,
    anomaly_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    allowed_server_ids: Optional[set[int]] = None,
):
    conds = _build_filters(
        server_id, anomaly_type, severity, status, date_from, date_to, allowed_server_ids
    )
    where = and_(*conds) if conds else None

    count_q = select(func.count()).select_from(Anomaly)
    if where is not None:
        count_q = count_q.where(where)
    total = int((await db.execute(count_q)).scalar_one())

    list_q = select(Anomaly).order_by(Anomaly.detected_at.desc()).offset(offset).limit(limit)
    if where is not None:
        list_q = list_q.where(where)
    items = list((await db.execute(list_q)).scalars().all())
    return items, total

@router.get("")
async def list_anomalies(
    server_id: Optional[int] = Query(None),
    anomaly_type: Optional[str] = Query(None, alias="type"),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None, alias="from"),
    date_to: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed_server_ids = await get_accessible_server_ids(db, current_user)
    items, total = await _query_anomalies(
        db,
        server_id=server_id,
        anomaly_type=anomaly_type,
        severity=severity,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        allowed_server_ids=allowed_server_ids,
    )
    return paginated(
        items=[AnomalyResponse.model_validate(a).model_dump() for a in items],
        limit=limit,
        offset=offset,
        total=total,
        message="Anomalies retrieved successfully",
    )

@router.get("/{anomaly_id}")
async def get_anomaly(
    anomaly_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    anomaly = (
        await db.execute(select(Anomaly).where(Anomaly.id == anomaly_id))
    ).scalar_one_or_none()
    if anomaly is None:
        raise NotFoundError("Anomaly not found")
    await assert_server_read_access(db, current_user, anomaly.server_id)
    return ok(
        data=AnomalyResponse.model_validate(anomaly).model_dump(),
        message="Anomaly retrieved successfully",
    )

@router.patch("/{anomaly_id}/status")
async def update_anomaly_status(
    anomaly_id: int,
    payload: AnomalyStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    anomaly = (
        await db.execute(select(Anomaly).where(Anomaly.id == anomaly_id))
    ).scalar_one_or_none()
    if anomaly is None:
        raise NotFoundError("Anomaly not found")
    await assert_server_read_access(db, current_user, anomaly.server_id)

    previous = anomaly.status
    anomaly.status = payload.status
    if payload.status == AnomalyStatus.RESOLVED.value:
        anomaly.resolved_at = datetime.utcnow()
        anomaly.resolved_by = current_user.id
    else:
        anomaly.resolved_at = None
        anomaly.resolved_by = None
    await db.commit()
    await db.refresh(anomaly)

    await AuditLogger.log(
        db,
        action=AuditAction.ANOMALY_STATUS_CHANGED.value,
        user=current_user,
        resource_type="anomaly",
        resource_id=anomaly.id,
        details={"from": previous, "to": payload.status},
        request=request,
    )
    return ok(
        data=AnomalyResponse.model_validate(anomaly).model_dump(),
        message="Anomaly status updated successfully",
    )

@direct_router.get("/servers/{server_id}/anomalies")
async def list_server_anomalies(
    server_id: int,
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assert_server_read_access(db, current_user, server_id)
    items, total = await _query_anomalies(
        db,
        server_id=server_id,
        severity=severity,
        status=status,
        limit=limit,
        offset=offset,
    )
    return paginated(
        items=[AnomalyResponse.model_validate(a).model_dump() for a in items],
        limit=limit,
        offset=offset,
        total=total,
        message="Server anomalies retrieved successfully",
    )
