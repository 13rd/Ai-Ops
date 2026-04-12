import asyncio
import json
import logging
import secrets
import socket
from datetime import datetime, timedelta
from typing import Dict, Optional
import threading
import weakref

import paramiko
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.console_session import ConsoleSession, ConsoleSessionStatus
from app.models.server import Server
from app.models.user import User
from app.services.servers.connection_service import SSHConnectionService


logger = logging.getLogger(__name__)


class ConsoleService:
    """
    Service for managing SSH console sessions through WebSocket gateway.
    """

    # Store active sessions - in production, you'd want to use Redis or similar for persistence
    _active_sessions: Dict[str, Dict] = {}

    # Timeout configurations
    SSH_CONNECTION_TIMEOUT = 30  # seconds
    SESSION_CLEANUP_INTERVAL = 300  # seconds (5 minutes)

    @classmethod
    async def start_session(
        cls, db: AsyncSession, user: User, server_id: int, client_ip: Optional[str] = None
    ) -> Optional[str]:
        """
        Start a new console session and return a session token.
        """
        # Get server by ID
        server_query = select(Server).where(Server.id == server_id)
        result = await db.execute(server_query)
        server = result.scalar_one_or_none()

        if not server:
            logger.error(f"Server with ID {server_id} not found")
            return None

        # Create session token
        session_token = secrets.token_urlsafe(32)

        # Create session record in DB
        session = ConsoleSession(
            session_token=session_token,
            user_id=user.id,
            server_id=server.id,
            status=ConsoleSessionStatus.ACTIVE,
            client_ip=client_ip,
            session_metadata=json.dumps({}),
        )

        db.add(session)
        await db.commit()
        await db.refresh(session)

        # Store in active sessions cache
        cls._active_sessions[session_token] = {
            "session_id": session.id,
            "user_id": user.id,
            "server_id": server.id,
            "server_details": server,
            "ssh_client": None,
            "ssh_shell": None,
            "is_connected": False,
            "last_activity": datetime.utcnow(),
            "connection_attempts": 0,
            "max_connection_attempts": 3,  # Max reconnect attempts
        }

        logger.info(
            f"Started console session {session_token} for user {user.id} on server {server_id}"
        )
        return session_token

    @classmethod
    async def connect_session(cls, session_token: str) -> Optional[paramiko.SSHClient]:
        """
        Connect to the server via SSH for a given session with retry logic.
        """
        if session_token not in cls._active_sessions:
            logger.error(f"Session {session_token} not found in active sessions")
            return None

        session_data = cls._active_sessions[session_token]

        # Check connection attempts
        if session_data["connection_attempts"] >= session_data["max_connection_attempts"]:
            logger.error(f"Max connection attempts reached for session {session_token}")
            return None

        try:
            # Get server details
            server = session_data["server_details"]

            # Create SSH client with timeout
            ssh_client = await SSHConnectionService.get_ssh_client(server)

            if not ssh_client:
                logger.error(f"Failed to create SSH client for server {server.id}")
                session_data["connection_attempts"] += 1
                return None

            # Get interactive shell with timeout
            ssh_shell = ssh_client.invoke_shell(term="xterm")
            # Set timeout for shell operations
            ssh_shell.settimeout(cls.SSH_CONNECTION_TIMEOUT)

            # Store SSH connection in session data
            session_data["ssh_client"] = ssh_client
            session_data["ssh_shell"] = ssh_shell
            session_data["is_connected"] = True
            session_data["connection_attempts"] = 0  # Reset on successful connection
            session_data["last_activity"] = datetime.utcnow()

            logger.info(f"Successfully connected SSH session {session_token}")
            return ssh_client

        except Exception as e:
            logger.error(f"Error connecting SSH session {session_token}: {e}")
            session_data["connection_attempts"] += 1
            if session_data["connection_attempts"] >= session_data["max_connection_attempts"]:
                await cls.terminate_session(
                    None, session_token, reason=f"Max connection attempts failed: {str(e)}"
                )
            return None

    @classmethod
    def get_session_data(cls, session_token: str) -> Optional[Dict]:
        """
        Get session data by token.
        """
        return cls._active_sessions.get(session_token)

    @classmethod
    def update_session_activity(cls, session_token: str):
        """
        Update the last activity timestamp for a session.
        """
        if session_token in cls._active_sessions:
            cls._active_sessions[session_token]["last_activity"] = datetime.utcnow()

    @classmethod
    async def cleanup_inactive_sessions(cls):
        """
        Clean up inactive sessions to prevent resource leaks.
        """
        current_time = datetime.utcnow()
        inactive_threshold = current_time - timedelta(
            seconds=cls.SSH_CONNECTION_TIMEOUT * 10
        )  # 10x timeout as threshold

        # Create a list of sessions to remove to prevent modification during iteration
        sessions_to_remove = []

        for token, session_data in cls._active_sessions.items():
            if session_data["last_activity"] < inactive_threshold:
                sessions_to_remove.append(token)

        for token in sessions_to_remove:
            logger.info(f"Cleaning up inactive session: {token}")
            await cls.terminate_session(None, token, "Inactive for too long")

    @classmethod
    async def send_to_session(cls, session_token: str, data: str) -> bool:
        """
        Send data to the SSH session.
        """
        session_data = cls._active_sessions.get(session_token)
        if not session_data or not session_data.get("is_connected"):
            logger.warning(f"Cannot send to disconnected session {session_token}")
            return False

        try:
            ssh_shell = session_data["ssh_shell"]
            ssh_shell.send(data.encode("utf-8"))
            cls.update_session_activity(session_token)
            return True
        except Exception as e:
            logger.error(f"Error sending to session {session_token}: {e}")
            await cls.terminate_session(None, session_token, reason=f"Send error: {str(e)}")
            return False

    @classmethod
    async def read_from_session(cls, session_token: str, size: int = 1024) -> Optional[str]:
        """
        Read data from the SSH session.
        """
        session_data = cls._active_sessions.get(session_token)
        if not session_data or not session_data.get("is_connected"):
            logger.warning(f"Cannot read from disconnected session {session_token}")
            return None

        try:
            ssh_shell = session_data["ssh_shell"]
            if ssh_shell.recv_ready():
                data = ssh_shell.recv(size)
                decoded_data = data.decode("utf-8")
                cls.update_session_activity(session_token)
                return decoded_data
            return None
        except Exception as e:
            logger.error(f"Error reading from session {session_token}: {e}")
            await cls.terminate_session(None, session_token, reason=f"Read error: {str(e)}")
            return None

    @classmethod
    async def terminate_session(
        cls, db: Optional[AsyncSession], session_token: str, reason: str = "Normal termination"
    ) -> bool:
        """
        Terminate a console session.
        """
        if session_token not in cls._active_sessions:
            logger.warning(f"Attempted to terminate non-existent session {session_token}")
            return False

        session_data = cls._active_sessions[session_token]

        # Close SSH connection if active
        ssh_shell = session_data.get("ssh_shell")
        ssh_client = session_data.get("ssh_client")

        if ssh_shell:
            try:
                ssh_shell.close()
            except Exception as e:
                logger.warning(f"Error closing SSH shell: {e}")

        if ssh_client:
            try:
                ssh_client.close()
            except Exception as e:
                logger.warning(f"Error closing SSH client: {e}")

        # Update database status if db session is provided
        if db is not None:
            # Determine the final status based on the reason
            if (
                "error" in reason.lower()
                or "failed" in reason.lower()
                or "timeout" in reason.lower()
            ):
                final_status = ConsoleSessionStatus.FAILED
            else:
                final_status = ConsoleSessionStatus.TERMINATED

            await cls.update_session_status(db, session_token, final_status, reason)

        # Remove from active sessions
        del cls._active_sessions[session_token]

        logger.info(f"Terminated console session {session_token}, reason: {reason}")
        return True

    @classmethod
    async def update_session_status(
        cls, db: AsyncSession, session_token: str, status: ConsoleSessionStatus, reason: str = None
    ) -> bool:
        """
        Update session status in database.
        """
        query = select(ConsoleSession).where(ConsoleSession.session_token == session_token)
        result = await db.execute(query)
        session_obj = result.scalar_one_or_none()

        if not session_obj:
            return False

        session_obj.status = status
        if reason:
            session_obj.termination_reason = reason

        # Calculate duration if ending
        if status in [
            ConsoleSessionStatus.COMPLETED,
            ConsoleSessionStatus.FAILED,
            ConsoleSessionStatus.TERMINATED,
        ]:
            if session_obj.started_at:
                duration = (datetime.utcnow() - session_obj.started_at).total_seconds()
                session_obj.duration_seconds = int(duration)
            session_obj.ended_at = datetime.utcnow()

        await db.commit()
        return True
