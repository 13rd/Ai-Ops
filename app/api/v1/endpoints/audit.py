from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.core.responses import paginated
from app.db.base import get_db
from app.models.user import User
from app.schemas.audit import AuditLogResponse
from app.services.audit.logger import AuditLogger

router = APIRouter()

@router.get("/audit-log")
async def list_audit_log(
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None, alias="from"),
    date_to: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    items, total = await AuditLogger.list_entries(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return paginated(
        items=[AuditLogResponse.model_validate(e).model_dump() for e in items],
        limit=limit,
        offset=offset,
        total=total,
        message="Audit log retrieved successfully",
    )
