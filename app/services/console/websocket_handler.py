import asyncio
import json
import logging
from typing import Dict, Set

import websockets
from websockets.exceptions import ConnectionClosed

from app.services.console.console_service import ConsoleService

logger = logging.getLogger(__name__)

connected_websockets: Set[websockets.WebSocketServerProtocol] = set()
session_websocket_map: Dict[str, websockets.WebSocketServerProtocol] = {}

async def console_websocket_handler(websocket: websockets.WebSocketServerProtocol, path: str):

    connected_websockets.add(websocket)
    logger.info(f"New WebSocket connection established: {websocket.remote_address}")

    try:
        init_msg = await websocket.recv()
        init_data = json.loads(init_msg)

        if init_data.get("action") != "init_session":
            await websocket.send(json.dumps({"error": "Invalid initialization message"}))
            return

        session_token = init_data.get("session_token")
        if not session_token:
            await websocket.send(json.dumps({"error": "Missing session token"}))
            return

        ssh_client = await ConsoleService.connect_session(session_token)
        if not ssh_client:
            await websocket.send(json.dumps({"error": "Failed to connect to server"}))
            return

        session_websocket_map[session_token] = websocket

        await websocket.send(json.dumps({"type": "connected", "session_token": session_token}))

        await handle_session_communication(websocket, session_token)

    except ConnectionClosed:
        logger.info(f"WebSocket connection closed: {websocket.remote_address}")
    except json.JSONDecodeError:
        logger.error("Received invalid JSON from WebSocket client")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
    finally:
        connected_websockets.discard(websocket)
        for s_token, ws in list(session_websocket_map.items()):
            if ws == websocket:
                del session_websocket_map[s_token]
                await ConsoleService.terminate_session(None, s_token, "WebSocket disconnected")

async def handle_session_communication(
    websocket: websockets.WebSocketServerProtocol, session_token: str
):

    try:
        tasks = [
            asyncio.create_task(forward_ssh_to_websocket(session_token, websocket)),
            asyncio.create_task(forward_websocket_to_ssh(session_token, websocket)),
        ]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

    except Exception as e:
        logger.error(f"Error in session communication: {e}")

async def forward_ssh_to_websocket(
    session_token: str, websocket: websockets.WebSocketServerProtocol
):

    try:
        while True:
            data = await ConsoleService.read_from_session(session_token)
            if data:
                await websocket.send(json.dumps({"type": "output", "data": data}))

            await asyncio.sleep(0.01)

    except ConnectionClosed:
        logger.info(f"WebSocket closed while reading SSH output for session {session_token}")
    except Exception as e:
        logger.error(f"Error forwarding SSH to WebSocket: {e}")

async def forward_websocket_to_ssh(
    session_token: str, websocket: websockets.WebSocketServerProtocol
):

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")

                if action == "input":
                    input_data = data.get("data", "")
                    success = await ConsoleService.send_to_session(session_token, input_data)
                    if not success:
                        await websocket.send(
                            json.dumps({"error": "Failed to send input to server"})
                        )
                        break
                elif action == "resize":
                    cols = data.get("cols", 80)
                    rows = data.get("rows", 24)
                    pass
                elif action == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                success = await ConsoleService.send_to_session(session_token, message)
                if not success:
                    break

    except ConnectionClosed:
        logger.info(f"WebSocket closed while reading input for session {session_token}")
    except Exception as e:
        logger.error(f"Error forwarding WebSocket to SSH: {e}")
