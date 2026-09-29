from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import ok
from app.db.base import get_db
from app.models.anomaly import Anomaly
from app.models.audit_log import AuditAction
from app.models.recommendation import Recommendation, RecommendationStatus
from app.models.user import User
from app.schemas.recommendation import RecommendationResponse
from app.services.audit.logger import AuditLogger

router = APIRouter()
anomaly_recs_router = APIRouter()

async def _get_recommendation(db: AsyncSession, rec_id: int) -> Recommendation:
    rec = (
        await db.execute(select(Recommendation).where(Recommendation.id == rec_id))
    ).scalar_one_or_none()
    if rec is None:
        raise NotFoundError("Recommendation not found")
    return rec

@anomaly_recs_router.get("/anomalies/{anomaly_id}/recommendations")
async def list_anomaly_recommendations(
    anomaly_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    anomaly = (
        await db.execute(select(Anomaly).where(Anomaly.id == anomaly_id))
    ).scalar_one_or_none()
    if anomaly is None:
        raise NotFoundError("Anomaly not found")

    result = await db.execute(
        select(Recommendation)
        .where(Recommendation.anomaly_id == anomaly_id)
        .order_by(Recommendation.created_at.desc())
    )
    items = list(result.scalars().all())
    return ok(
        data=[RecommendationResponse.model_validate(r).model_dump() for r in items],
        message="Recommendations retrieved successfully",
    )

@router.post("/{recommendation_id}/approve")
async def approve_recommendation(
    recommendation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rec = await _get_recommendation(db, recommendation_id)
    if rec.status != RecommendationStatus.PENDING.value:
        raise ValidationError(
            f"Recommendation is not pending (current status: {rec.status})",
            code="recommendation_not_pending",
        )
    rec.status = RecommendationStatus.APPROVED.value
    rec.approved_by = current_user.id
    await db.commit()
    await db.refresh(rec)

    await AuditLogger.log(
        db,
        action=AuditAction.RECOMMENDATION_APPROVED.value,
        user=current_user,
        resource_type="recommendation",
        resource_id=rec.id,
        details={"anomaly_id": rec.anomaly_id, "command": rec.filtered_command},
        request=request,
    )
    return ok(
        data=RecommendationResponse.model_validate(rec).model_dump(),
        message="Recommendation approved successfully",
    )

@router.post("/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rec = await _get_recommendation(db, recommendation_id)
    if rec.status != RecommendationStatus.PENDING.value:
        raise ValidationError(
            f"Recommendation is not pending (current status: {rec.status})",
            code="recommendation_not_pending",
        )
    rec.status = RecommendationStatus.REJECTED.value
    rec.approved_by = current_user.id
    rec.execution_result = {"rejected_at": datetime.utcnow().isoformat()}
    await db.commit()
    await db.refresh(rec)

    await AuditLogger.log(
        db,
        action=AuditAction.RECOMMENDATION_REJECTED.value,
        user=current_user,
        resource_type="recommendation",
        resource_id=rec.id,
        details={"anomaly_id": rec.anomaly_id},
        request=request,
    )
    return ok(
        data=RecommendationResponse.model_validate(rec).model_dump(),
        message="Recommendation rejected successfully",
    )
