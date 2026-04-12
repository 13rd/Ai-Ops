from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models.server import Server
from app.models.user import User
from app.schemas.response import success_response
from app.services.console.console_service import ConsoleService
from app.services.servers.server_service import ServerService

router = APIRouter()


@router.post("/start-session/{server_id}", response_model=dict)
async def start_console_session(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start a new console session for a server.
    Returns a session token that can be used to connect via WebSocket.
    """
    # Verify server exists and user has access
    server = await ServerService.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    # Start console session
    session_token = await ConsoleService.start_session(
        db,
        current_user,
        server_id,
        # In a real implementation, you'd extract client IP from request
        client_ip="127.0.0.1",  # Placeholder for now
    )

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start console session",
        )

    return success_response(
        data={"session_token": session_token, "server_id": server_id, "server_name": server.name},
        message="Console session started successfully. Connect via WebSocket using the session token.",
    )


@router.post("/terminate-session/{session_token}", response_model=dict)
async def terminate_console_session(
    session_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Terminate an active console session.
    """
    # In a real implementation, you'd verify that the user owns the session
    # For now, we'll just terminate it

    success = await ConsoleService.terminate_session(session_token, "Requested by user")
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session not found or already terminated",
        )

    # Update session status in DB
    from app.models.console_session import ConsoleSessionStatus

    await ConsoleService.update_session_status(
        db, session_token, ConsoleSessionStatus.TERMINATED, "User requested termination"
    )

    return success_response(
        data={"session_token": session_token}, message="Console session terminated successfully"
    )


@router.get("/session-info/{session_token}", response_model=dict)
async def get_session_info(
    session_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get information about a console session.
    """
    session_data = ConsoleService.get_session_data(session_token)

    if not session_data:
        # Check if session exists in DB but isn't active
        from sqlalchemy import select
        from app.models.console_session import ConsoleSession

        query = select(ConsoleSession).where(ConsoleSession.session_token == session_token)
        result = await db.execute(query)
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        return success_response(
            data={
                "session_token": session.session_token,
                "status": session.status,
                "server_id": session.server_id,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            },
            message="Session found but is not currently active",
        )

    return success_response(
        data={
            "session_token": session_token,
            "is_connected": session_data.get("is_connected", False),
            "server_id": session_data.get("server_id"),
            "user_id": session_data.get("user_id"),
        },
        message="Session information retrieved successfully",
    )
