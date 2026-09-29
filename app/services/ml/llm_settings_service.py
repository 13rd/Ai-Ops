from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_settings import LLMSettings
from app.models.user import User

SETTINGS_ID = 1

_UPDATABLE_FIELDS = (
    "enabled",
    "model",
    "timeout_sec",
    "keep_alive",
    "prompt_template",
    "extra",
)

async def get_settings(db: AsyncSession) -> LLMSettings:

    row = (
        await db.execute(select(LLMSettings).where(LLMSettings.id == SETTINGS_ID))
    ).scalar_one_or_none()
    if row is None:
        row = LLMSettings(id=SETTINGS_ID)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row

async def update_settings(
    db: AsyncSession, payload: dict[str, Any], user: User
) -> LLMSettings:

    row = await get_settings(db)
    for field in _UPDATABLE_FIELDS:
        if field in payload:
            setattr(row, field, payload[field])
    row.updated_by = user.id
    await db.commit()
    await db.refresh(row)
    return row
