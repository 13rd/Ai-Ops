import asyncio
import json
import logging
from typing import Dict, Set

import websockets
from websockets.exceptions import ConnectionClosed

from app.services.console.console_service import ConsoleService

logger = logging.getLogger(__name__)

# Store active WebSocket connections
connected_websockets: Set[websockets.WebSocketServerProtocol] = set()
session_websocket_map: Dict[str, websockets.WebSocketServerProtocol] = {}


async def console_websocket_handler(websocket: websockets.WebSocketServerProtocol, path: str):
    """
    WebSocket handler for console sessions.
    Handles the communication between browser client and SSH server.
    """
    # Add to connected websockets
    connected_websockets.add(websocket)
    logger.info(f"New WebSocket connection established: {websocket.remote_address}")

    try:
        # Wait for session initialization message from client
        init_msg = await websocket.recv()
        init_data = json.loads(init_msg)

        if init_data.get("action") != "init_session":
            await websocket.send(json.dumps({"error": "Invalid initialization message"}))
            return

        session_token = init_data.get("session_token")
        if not session_token:
            await websocket.send(json.dumps({"error": "Missing session token"}))
            return

        # Connect to SSH session
        ssh_client = await ConsoleService.connect_session(session_token)
        if not ssh_client:
            await websocket.send(json.dumps({"error": "Failed to connect to server"}))
            return

        # Register this websocket for the session
        session_websocket_map[session_token] = websocket

        # Send success confirmation
        await websocket.send(json.dumps({"type": "connected", "session_token": session_token}))

        # Start bidirectional communication
        await handle_session_communication(websocket, session_token)

    except ConnectionClosed:
        logger.info(f"WebSocket connection closed: {websocket.remote_address}")
    except json.JSONDecodeError:
        logger.error("Received invalid JSON from WebSocket client")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
    finally:
        # Cleanup
        connected_websockets.discard(websocket)
        # Remove from session map if exists
        for s_token, ws in list(session_websocket_map.items()):
            if ws == websocket:
                del session_websocket_map[s_token]
                # Terminate the SSH session (db session is None here, so only in-memory cleanup)
                await ConsoleService.terminate_session(None, s_token, "WebSocket disconnected")


async def handle_session_communication(
    websocket: websockets.WebSocketServerProtocol, session_token: str
):
    """
    Handle bidirectional communication between WebSocket and SSH session.
    """
    try:
        # Create tasks for reading from SSH and WebSocket
        tasks = [
            asyncio.create_task(forward_ssh_to_websocket(session_token, websocket)),
            asyncio.create_task(forward_websocket_to_ssh(session_token, websocket)),
        ]

        # Wait for either task to complete (due to error)
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Cancel remaining tasks
        for task in pending:
            task.cancel()

    except Exception as e:
        logger.error(f"Error in session communication: {e}")


async def forward_ssh_to_websocket(
    session_token: str, websocket: websockets.WebSocketServerProtocol
):
    """
    Forward data from SSH session to WebSocket client.
    """
    try:
        while True:
            # Read from SSH session
            data = await ConsoleService.read_from_session(session_token)
            if data:
                await websocket.send(json.dumps({"type": "output", "data": data}))

            # Small delay to prevent busy waiting
            await asyncio.sleep(0.01)

    except ConnectionClosed:
        logger.info(f"WebSocket closed while reading SSH output for session {session_token}")
    except Exception as e:
        logger.error(f"Error forwarding SSH to WebSocket: {e}")


async def forward_websocket_to_ssh(
    session_token: str, websocket: websockets.WebSocketServerProtocol
):
    """
    Forward data from WebSocket client to SSH session.
    """
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")

                if action == "input":
                    input_data = data.get("data", "")
                    # Send input to SSH session
                    success = await ConsoleService.send_to_session(session_token, input_data)
                    if not success:
                        await websocket.send(
                            json.dumps({"error": "Failed to send input to server"})
                        )
                        break
                elif action == "resize":
                    # Handle terminal resize if needed
                    cols = data.get("cols", 80)
                    rows = data.get("rows", 24)
                    # Terminal resize not implemented in this version
                    pass
                elif action == "ping":
                    # Respond to ping
                    await websocket.send(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                # Raw input data
                success = await ConsoleService.send_to_session(session_token, message)
                if not success:
                    break

    except ConnectionClosed:
        logger.info(f"WebSocket closed while reading input for session {session_token}")
    except Exception as e:
        logger.error(f"Error forwarding WebSocket to SSH: {e}")
