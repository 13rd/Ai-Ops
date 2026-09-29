from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.responses import ok, paginated
from app.db.base import get_db
from app.models.notification import Notification, NotificationChannel
from app.models.user import User
from app.schemas.notification import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationResponse,
)

router = APIRouter()

@router.get("")
async def list_notifications(
    is_read: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conds = [Notification.user_id == current_user.id]
    if is_read is not None:
        conds.append(Notification.is_read.is_(is_read))
    where = and_(*conds)

    total = int(
        (await db.execute(select(func.count()).select_from(Notification).where(where))).scalar_one()
    )
    items = list(
        (
            await db.execute(
                select(Notification)
                .where(where)
                .order_by(Notification.sent_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
    )
    return paginated(
        items=[NotificationResponse.model_validate(n).model_dump() for n in items],
        limit=limit,
        offset=offset,
        total=total,
        message="Notifications retrieved successfully",
    )

@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = (
        await db.execute(select(Notification).where(Notification.id == notification_id))
    ).scalar_one_or_none()
    if n is None:
        raise NotFoundError("Notification not found")
    if n.user_id != current_user.id:
        raise PermissionDeniedError("Not your notification")

    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.utcnow()
        await db.commit()
        await db.refresh(n)
    return ok(
        data=NotificationResponse.model_validate(n).model_dump(),
        message="Notification marked as read",
    )

@router.get("/channels")
async def list_my_channels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        await db.execute(
            select(NotificationChannel).where(NotificationChannel.user_id == current_user.id)
        )
    ).scalars().all()
    return ok(
        data=[NotificationChannelResponse.model_validate(r).model_dump() for r in rows],
        message="Notification channels retrieved successfully",
    )

@router.post("/channels")
async def create_my_channel(
    payload: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (
        await db.execute(
            select(NotificationChannel).where(
                NotificationChannel.user_id == current_user.id,
                NotificationChannel.channel_type == payload.channel_type,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.config = payload.config
        existing.enabled = payload.enabled
        existing.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(existing)
        row = existing
    else:
        row = NotificationChannel(
            user_id=current_user.id,
            channel_type=payload.channel_type,
            config=payload.config,
            enabled=payload.enabled,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)

    return ok(
        data=NotificationChannelResponse.model_validate(row).model_dump(),
        message="Notification channel saved",
    )

@router.patch("/channels/{channel_id}")
async def update_my_channel(
    channel_id: int,
    payload: NotificationChannelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(NotificationChannel).where(NotificationChannel.id == channel_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Notification channel not found")
    if row.user_id != current_user.id:
        raise PermissionDeniedError("Not your channel")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(row, field, value)
    row.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(row)
    return ok(
        data=NotificationChannelResponse.model_validate(row).model_dump(),
        message="Notification channel updated",
    )

@router.delete("/channels/{channel_id}")
async def delete_my_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(NotificationChannel).where(NotificationChannel.id == channel_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Notification channel not found")
    if row.user_id != current_user.id:
        raise PermissionDeniedError("Not your channel")
    await db.delete(row)
    await db.commit()
    return ok(data={"channel_id": channel_id}, message="Notification channel deleted")
