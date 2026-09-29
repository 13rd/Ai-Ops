from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationChannelType
from app.services.cache.redis import get_redis_client

logger = logging.getLogger(__name__)

def _channel(user_id: int) -> str:
    return f"notifications:user:{user_id}"

class InAppSender:
    @staticmethod
    async def send(
        db: AsyncSession,
        *,
        user_id: int,
        title: str,
        body: str,
        severity: str = "medium",
        anomaly_id: Optional[int] = None,
        also_telegram: bool = False,
    ) -> Notification:
        channels_sent: list[str] = [NotificationChannelType.INAPP.value]
        if also_telegram:
            channels_sent.append(NotificationChannelType.TELEGRAM.value)

        row = Notification(
            user_id=user_id,
            anomaly_id=anomaly_id,
            title=title,
            body=body,
            severity=severity,
            sent_at=datetime.utcnow(),
            channels_sent=channels_sent,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)

        try:
            await get_redis_client().publish(
                _channel(user_id),
                {
                    "id": row.id,
                    "title": row.title,
                    "body": row.body,
                    "severity": row.severity,
                    "anomaly_id": row.anomaly_id,
                    "sent_at": row.sent_at.isoformat(),
                },
            )
        except Exception:
            logger.exception("Publish notification to Redis failed for user %s", user_id)

        return row
