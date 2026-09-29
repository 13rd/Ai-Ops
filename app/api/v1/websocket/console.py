from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.base import AsyncSessionLocal
from app.models.audit_log import AuditAction
from app.models.console_session import ConsoleSession, ConsoleSessionStatus
from app.models.server import Server
from app.models.user import User, UserRole
from app.models.user_server_access import UserServerAccess
from app.services.audit.logger import AuditLogger
from app.services.servers.connection_service import SSHConnectionService

logger = logging.getLogger(__name__)
router = APIRouter()

WS_CLOSE_AUTH = 4401
WS_CLOSE_FORBIDDEN = 4403
WS_CLOSE_NOT_FOUND = 4404
WS_CLOSE_SSH_FAILED = 4500

_POLL_INTERVAL_SEC = 0.02
_RECV_BUF = 4096

@router.websocket("/ws/servers/{server_id}/console")
async def console_endpoint(
    websocket: WebSocket,
    server_id: int,
    token: str = Query(..., description="JWT access token"),
):
    await websocket.accept()
    session_token = f"ws-{datetime.utcnow().timestamp():.6f}-{server_id}"

    user: Optional[User] = None
    server: Optional[Server] = None
    can_write: bool = False
    async with AsyncSessionLocal() as setup_db:
        user = await _resolve_user(setup_db, token)
        if user is None:
            await _close(websocket, WS_CLOSE_AUTH, "invalid_token")
            return

        server = (
            await setup_db.execute(select(Server).where(Server.id == server_id))
        ).scalar_one_or_none()
        if server is None:
            await _close(websocket, WS_CLOSE_NOT_FOUND, "server_not_found")
            return

        access = await _resolve_access(setup_db, user, server_id)
        if access is None:
            await _close(websocket, WS_CLOSE_FORBIDDEN, "no_access")
            return
        can_write = access == "write"

        client_host = websocket.client.host if websocket.client else None
        session_row = ConsoleSession(
            session_token=session_token,
            user_id=user.id,
            server_id=server.id,
            status=ConsoleSessionStatus.ACTIVE.value,
            client_ip=client_host,
            session_metadata=json.dumps({"transport": "ws", "read_only": not can_write}),
        )
        setup_db.add(session_row)
        await setup_db.commit()
        await setup_db.refresh(session_row)
        session_db_id = session_row.id

        await AuditLogger.log(
            setup_db,
            action=AuditAction.CONSOLE_OPENED.value,
            user=user,
            resource_type="server",
            resource_id=server.id,
            details={"session_token": session_token, "read_only": not can_write},
            request=None,
        )

    loop = asyncio.get_event_loop()
    try:
        ssh_client = await SSHConnectionService.get_ssh_client(server)
    except Exception as exc:
        logger.warning("Console SSH open failed for server %s: %s", server.id, exc)
        await _send_json(websocket, {"type": "error", "data": f"SSH error: {exc}"})
        await _finalise_session(session_db_id, ConsoleSessionStatus.FAILED, str(exc))
        await _close(websocket, WS_CLOSE_SSH_FAILED, "ssh_failed")
        return

    try:
        channel = await loop.run_in_executor(
            None, lambda: ssh_client.invoke_shell(term="xterm-256color")
        )
        channel.setblocking(False)
    except Exception as exc:
        logger.warning("Console invoke_shell failed: %s", exc)
        await _send_json(websocket, {"type": "error", "data": f"PTY error: {exc}"})
        try:
            ssh_client.close()
        except Exception:
            pass
        await _finalise_session(session_db_id, ConsoleSessionStatus.FAILED, str(exc))
        await _close(websocket, WS_CLOSE_SSH_FAILED, "pty_failed")
        return

    await _send_json(
        websocket,
        {"type": "ready", "data": {"server_name": server.name, "read_only": not can_write}},
    )

    stop = asyncio.Event()
    termination_reason = "normal"

    async def ssh_to_ws():
        while not stop.is_set():
            try:
                if channel.recv_ready():
                    data = await loop.run_in_executor(None, lambda: channel.recv(_RECV_BUF))
                    if not data:
                        break
                    await _send_json(
                        websocket,
                        {"type": "output", "data": data.decode("utf-8", errors="replace")},
                    )
                elif channel.exit_status_ready():
                    break
                else:
                    await asyncio.sleep(_POLL_INTERVAL_SEC)
            except Exception as exc:
                logger.debug("ssh_to_ws stopped: %s", exc)
                break
        stop.set()

    async def ws_to_ssh():
        nonlocal termination_reason
        while not stop.is_set():
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                termination_reason = "client_disconnect"
                break

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _send_json(websocket, {"type": "error", "data": "invalid_json"})
                continue

            msg_type = message.get("type")
            if msg_type == "input":
                if not can_write:
                    await _send_json(
                        websocket,
                        {"type": "error", "data": "read_only_mode"},
                    )
                    continue
                payload = message.get("data", "")
                if not isinstance(payload, str) or not payload:
                    continue
                await _audit_input(user, server, session_token, payload)
                try:
                    await loop.run_in_executor(None, lambda: channel.send(payload.encode("utf-8")))
                except Exception as exc:
                    await _send_json(websocket, {"type": "error", "data": f"send_failed: {exc}"})
                    termination_reason = f"send_error: {exc}"
                    break
            elif msg_type == "resize":
                cols = int(message.get("cols") or 80)
                rows = int(message.get("rows") or 24)
                try:
                    await loop.run_in_executor(None, lambda: channel.resize_pty(cols, rows))
                except Exception:
                    pass
            else:
                await _send_json(websocket, {"type": "error", "data": "unknown_message_type"})
        stop.set()

    try:
        await asyncio.gather(ssh_to_ws(), ws_to_ssh())
    except Exception as exc:
        logger.exception("Console pump error")
        termination_reason = f"pump_error: {exc}"
    finally:
        try:
            channel.close()
        except Exception:
            pass
        try:
            ssh_client.close()
        except Exception:
            pass

        await _finalise_session(
            session_db_id,
            ConsoleSessionStatus.COMPLETED
            if termination_reason == "normal" or termination_reason == "client_disconnect"
            else ConsoleSessionStatus.FAILED,
            termination_reason,
        )
        async with AsyncSessionLocal() as audit_db:
            await AuditLogger.log(
                audit_db,
                action=AuditAction.CONSOLE_CLOSED.value,
                user=user,
                resource_type="server",
                resource_id=server.id,
                details={"session_token": session_token, "reason": termination_reason},
            )
        await _send_json(websocket, {"type": "closed", "data": termination_reason})
        try:
            await websocket.close()
        except Exception:
            pass

async def _resolve_user(db: AsyncSession, token: str) -> Optional[User]:
    payload = decode_access_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user

async def _resolve_access(db: AsyncSession, user: User, server_id: int) -> Optional[str]:

    if user.role == UserRole.ADMIN.value:
        return "write"
    row = (
        await db.execute(
            select(UserServerAccess).where(
                UserServerAccess.user_id == user.id,
                UserServerAccess.server_id == server_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return row.permission

async def _send_json(websocket: WebSocket, message: dict) -> None:
    try:
        await websocket.send_text(json.dumps(message))
    except Exception:
        pass

async def _close(websocket: WebSocket, code: int, reason: str) -> None:
    try:
        await websocket.send_text(json.dumps({"type": "error", "data": reason}))
    except Exception:
        pass
    try:
        await websocket.close(code=code)
    except Exception:
        pass

async def _audit_input(user: User, server: Server, session_token: str, payload: str) -> None:

    async with AsyncSessionLocal() as db:
        await AuditLogger.log(
            db,
            action=AuditAction.CONSOLE_COMMAND.value,
            user=user,
            resource_type="server",
            resource_id=server.id,
            details={
                "session_token": session_token,
                "input": payload if len(payload) <= 512 else payload[:512] + "…",
            },
        )

async def _finalise_session(
    session_db_id: int,
    status: ConsoleSessionStatus,
    reason: str,
) -> None:
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(ConsoleSession).where(ConsoleSession.id == session_db_id))
        ).scalar_one_or_none()
        if row is None:
            return
        row.status = status.value
        row.termination_reason = reason
        if row.started_at:
            row.duration_seconds = int((datetime.utcnow() - row.started_at).total_seconds())
        row.ended_at = datetime.utcnow()
        await db.commit()
