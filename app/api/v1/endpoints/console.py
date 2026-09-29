from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import AppException, NotFoundError, ValidationError
from app.core.responses import ok
from app.db.base import get_db
from app.models.console_session import ConsoleSession, ConsoleSessionStatus
from app.models.user import User
from app.services.console.console_service import ConsoleService
from app.services.servers.server_service import ServerService

router = APIRouter()

@router.post("/start-session/{server_id}")
async def start_console_session(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise NotFoundError("Server not found")

    session_token = await ConsoleService.start_session(
        db,
        current_user,
        server_id,
        client_ip="127.0.0.1",
    )
    if not session_token:
        raise AppException(
            "Failed to start console session",
            code="console_session_start_failed",
            status_code=500,
        )

    return ok(
        data={"session_token": session_token, "server_id": server_id, "server_name": server.name},
        message="Console session started. Connect via WebSocket using the session token.",
    )

@router.post("/terminate-session/{session_token}")
async def terminate_console_session(
    session_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = await ConsoleService.terminate_session(session_token, "Requested by user")
    if not success:
        raise ValidationError(
            "Session not found or already terminated",
            code="session_not_active",
        )

    await ConsoleService.update_session_status(
        db, session_token, ConsoleSessionStatus.TERMINATED, "User requested termination"
    )
    return ok(
        data={"session_token": session_token},
        message="Console session terminated successfully",
    )

@router.get("/session-info/{session_token}")
async def get_session_info(
    session_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_data = ConsoleService.get_session_data(session_token)

    if not session_data:
        query = select(ConsoleSession).where(ConsoleSession.session_token == session_token)
        result = await db.execute(query)
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError("Session not found")

        return ok(
            data={
                "session_token": session.session_token,
                "status": session.status,
                "server_id": session.server_id,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            },
            message="Session found but is not currently active",
        )

    return ok(
        data={
            "session_token": session_token,
            "is_connected": session_data.get("is_connected", False),
            "server_id": session_data.get("server_id"),
            "user_id": session_data.get("user_id"),
        },
        message="Session information retrieved successfully",
    )
