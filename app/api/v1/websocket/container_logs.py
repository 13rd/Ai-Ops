from __future__ import annotations

import asyncio
import json
import logging
import threading

import paramiko
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.base import AsyncSessionLocal
from app.models.server import Server
from app.models.user import User, UserRole
from app.models.user_server_access import ServerPermission, UserServerAccess
from app.services.servers.connection_service import SSHConnectionService

logger = logging.getLogger(__name__)
router = APIRouter()

WS_CLOSE_AUTH = 4401
WS_CLOSE_FORBIDDEN = 4403
WS_CLOSE_NOT_FOUND = 4404
WS_CLOSE_SSH_FAILED = 4500

_SENTINEL = object()

async def _resolve_user(db: AsyncSession, token: str):
    payload = decode_access_token(token)
    if payload is None:
        return None
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user

async def _has_write_access(db: AsyncSession, user: User, server_id: int) -> bool:
    if user.role == UserRole.ADMIN.value:
        return True
    row = (
        await db.execute(
            select(UserServerAccess).where(
                UserServerAccess.user_id == user.id,
                UserServerAccess.server_id == server_id,
            )
        )
    ).scalar_one_or_none()
    return row is not None and row.permission == ServerPermission.WRITE.value

async def _send(ws: WebSocket, msg: dict) -> None:
    try:
        await ws.send_text(json.dumps(msg))
    except Exception:
        pass

async def _close(ws: WebSocket, code: int, reason: str) -> None:
    await _send(ws, {"type": "error", "data": reason})
    try:
        await ws.close(code=code)
    except Exception:
        pass

def _stream_logs_thread(
    client: paramiko.SSHClient,
    container_id: str,
    tail: int,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
    stop_event: threading.Event,
) -> None:
    try:
        cmd = f"docker logs --follow --tail {tail} {container_id} 2>&1"
        _, stdout, _ = client.exec_command(cmd)
        for line in stdout:
            if stop_event.is_set():
                break
            asyncio.run_coroutine_threadsafe(
                queue.put(line.rstrip("\n")), loop
            ).result(timeout=2)
    except Exception as e:
        asyncio.run_coroutine_threadsafe(queue.put(f"[stream error] {e}"), loop)
    finally:
        asyncio.run_coroutine_threadsafe(queue.put(_SENTINEL), loop)
        try:
            client.close()
        except Exception:
            pass

@router.websocket("/ws/servers/{server_id}/containers/{container_id}/logs")
async def container_logs_endpoint(
    websocket: WebSocket,
    server_id: int,
    container_id: str,
    token: str = Query(...),
    tail: int = Query(50, ge=1, le=2000),
):
    await websocket.accept()

    async with AsyncSessionLocal() as db:
        user = await _resolve_user(db, token)
        if user is None:
            await _close(websocket, WS_CLOSE_AUTH, "invalid_token")
            return

        if not await _has_write_access(db, user, server_id):
            await _close(websocket, WS_CLOSE_FORBIDDEN, "forbidden")
            return

        server = (
            await db.execute(select(Server).where(Server.id == server_id))
        ).scalar_one_or_none()
        if server is None:
            await _close(websocket, WS_CLOSE_NOT_FOUND, "server_not_found")
            return

        try:
            client = await SSHConnectionService.get_ssh_client(server)
        except Exception as e:
            logger.error(f"SSH failed for server {server_id}: {e}")
            await _close(websocket, WS_CLOSE_SSH_FAILED, "ssh_failed")
            return

    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    stop_event = threading.Event()
    loop = asyncio.get_event_loop()

    thread = threading.Thread(
        target=_stream_logs_thread,
        args=(client, container_id, tail, queue, loop, stop_event),
        daemon=True,
    )
    thread.start()

    try:
        while True:
            item = await asyncio.wait_for(queue.get(), timeout=30)
            if item is _SENTINEL:
                await _send(websocket, {"type": "closed", "data": "stream_ended"})
                break
            await _send(websocket, {"type": "log", "data": item})
    except asyncio.TimeoutError:
        await _send(websocket, {"type": "closed", "data": "timeout"})
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        try:
            await websocket.close()
        except Exception:
            pass
