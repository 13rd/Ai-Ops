from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.core.responses import ok
from app.db.base import get_db
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.llm_settings import LLMSettingsResponse, LLMSettingsUpdate
from app.services.audit.logger import AuditLogger
from app.services.ml.llm_settings_service import get_settings, update_settings

router = APIRouter()

@router.get("")
async def get_llm_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    settings_row = await get_settings(db)
    return ok(
        data=LLMSettingsResponse.model_validate(settings_row).model_dump(),
        message="LLM settings retrieved successfully",
    )

@router.put("")
async def update_llm_settings(
    payload: LLMSettingsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    settings_row = await update_settings(
        db, payload.model_dump(exclude_unset=True), current_user
    )

    await AuditLogger.log(
        db,
        action=AuditAction.LLM_SETTINGS_UPDATED.value,
        user=current_user,
        resource_type="llm_settings",
        resource_id=settings_row.id,
        details=payload.model_dump(exclude_unset=True),
        request=request,
    )
    return ok(
        data=LLMSettingsResponse.model_validate(settings_row).model_dump(),
        message="LLM settings updated successfully",
    )
