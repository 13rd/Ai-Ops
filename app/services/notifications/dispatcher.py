from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import Anomaly
from app.models.notification import NotificationChannel, NotificationChannelType
from app.models.server import Server
from app.models.user import User, UserRole
from app.models.user_server_access import UserServerAccess
from app.services.notifications.inapp import InAppSender
from app.services.notifications.telegram import TelegramSender, render_anomaly_message

logger = logging.getLogger(__name__)

@dataclass
class NotificationEvent:
    title: str
    body: str
    severity: str = "medium"
    anomaly_id: Optional[int] = None

class NotificationDispatcher:
    @staticmethod
    async def dispatch_for_user(
        db: AsyncSession,
        user: User,
        event: NotificationEvent,
    ) -> None:

        channels = (
            await db.execute(
                select(NotificationChannel).where(
                    NotificationChannel.user_id == user.id,
                    NotificationChannel.enabled.is_(True),
                )
            )
        ).scalars().all()

        telegram_chat_id = None
        for ch in channels:
            if ch.channel_type == NotificationChannelType.TELEGRAM.value:
                telegram_chat_id = (ch.config or {}).get("chat_id")

        await InAppSender.send(
            db,
            user_id=user.id,
            title=event.title,
            body=event.body,
            severity=event.severity,
            anomaly_id=event.anomaly_id,
            also_telegram=bool(telegram_chat_id),
        )

        if telegram_chat_id and TelegramSender.is_configured():
            await TelegramSender.send(telegram_chat_id, f"{event.title}\n\n{event.body}")

    @staticmethod
    async def dispatch_anomaly(
        db: AsyncSession,
        anomaly: Anomaly,
    ) -> int:

        server = (
            await db.execute(select(Server).where(Server.id == anomaly.server_id))
        ).scalar_one_or_none()
        server_name = server.name if server else f"server #{anomaly.server_id}"
        server_host = server.host if server else None

        title = (
            f"[{anomaly.severity.upper()}] "
            f"{anomaly.anomaly_type.replace('_', ' ').title()} on {server_name}"
        )
        body = render_anomaly_message(
            server_name=server_name,
            server_host=server_host,
            anomaly_type=anomaly.anomaly_type,
            severity=anomaly.severity,
        )
        event = NotificationEvent(
            title=title,
            body=body,
            severity=anomaly.severity,
            anomaly_id=anomaly.id,
        )

        recipients = await _resolve_recipients(db, anomaly.server_id)
        for user in recipients:
            try:
                await NotificationDispatcher.dispatch_for_user(db, user, event)
            except Exception:
                logger.exception("Failed dispatching anomaly %s to user %s", anomaly.id, user.id)
        return len(recipients)

    @staticmethod
    async def dispatch_server_event(
        db: AsyncSession,
        server_id: int,
        title: str,
        body: str,
        severity: str = "low",
    ) -> int:

        event = NotificationEvent(title=title, body=body, severity=severity)
        recipients = await _resolve_recipients(db, server_id)
        for user in recipients:
            try:
                await NotificationDispatcher.dispatch_for_user(db, user, event)
            except Exception:
                logger.exception(
                    "Failed dispatching server event %r to user %s", title, user.id
                )
        return len(recipients)

async def _resolve_recipients(db: AsyncSession, server_id: int) -> list[User]:

    admins = list(
        (await db.execute(
            select(User).where(User.role == UserRole.ADMIN.value, User.is_active.is_(True))
        )).scalars().all()
    )

    operator_ids = list(
        (await db.execute(
            select(UserServerAccess.user_id).where(UserServerAccess.server_id == server_id)
        )).scalars().all()
    )
    operators: list[User] = []
    if operator_ids:
        operators = list(
            (await db.execute(
                select(User).where(
                    User.id.in_(operator_ids),
                    User.role == UserRole.OPERATOR.value,
                    User.is_active.is_(True),
                )
            )).scalars().all()
        )

    seen: set[int] = set()
    recipients: list[User] = []
    for u in admins + operators:
        if u.id in seen:
            continue
        seen.add(u.id)
        recipients.append(u)
    return recipients
