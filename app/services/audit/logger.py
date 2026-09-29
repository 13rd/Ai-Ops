from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import Request
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)

class AuditLogger:

    @staticmethod
    async def log(
        db: AsyncSession,
        *,
        action: str,
        user: Optional[User] = None,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[Any] = None,
        details: Optional[dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> None:
        try:
            ip = None
            ua = None
            if request is not None:
                ip = request.client.host if request.client else None
                ua = request.headers.get("user-agent")

            entry = AuditLog(
                user_id=user.id if user else user_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                details=details or {},
                ip_address=ip,
                user_agent=ua,
                created_at=datetime.utcnow(),
            )
            db.add(entry)
            await db.commit()
        except Exception:
            logger.exception("Failed to write audit log entry for action=%s", action)
            try:
                await db.rollback()
            except Exception:
                pass

    @staticmethod
    async def list_entries(
        db: AsyncSession,
        *,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        conds = []
        if user_id is not None:
            conds.append(AuditLog.user_id == user_id)
        if action is not None:
            conds.append(AuditLog.action == action)
        if resource_type is not None:
            conds.append(AuditLog.resource_type == resource_type)
        if date_from is not None:
            conds.append(AuditLog.created_at >= date_from)
        if date_to is not None:
            conds.append(AuditLog.created_at <= date_to)

        where = and_(*conds) if conds else None

        count_q = select(func.count()).select_from(AuditLog)
        if where is not None:
            count_q = count_q.where(where)
        total = int((await db.execute(count_q)).scalar_one())

        list_q = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        if where is not None:
            list_q = list_q.where(where)
        items = list((await db.execute(list_q)).scalars().all())
        return items, total
