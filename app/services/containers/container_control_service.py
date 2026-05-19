import asyncio
import logging
from typing import Optional

import paramiko
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.container import ContainerSnapshot
from app.models.server import Server
from app.services.servers.connection_service import SSHConnectionService

logger = logging.getLogger(__name__)


class ContainerControlService:
    """
    Service for controlling containers (start, stop, restart) on remote servers.
    """

    @staticmethod
    async def start_container(db: AsyncSession, server_id: int, container_id: str) -> bool:
        """
        Start a container on a server.
        """
        server = await ContainerControlService._get_server_by_id(db, server_id)
        if not server:
            logger.error(f"Server with ID {server_id} not found")
            return False

        try:
            client = await SSHConnectionService.get_ssh_client(server)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, ContainerControlService._start_container_sync, client, container_id
            )
            client.close()
            return success
        except Exception as e:
            logger.error(f"Error starting container {container_id} on server {server_id}: {e}")
            return False

    @staticmethod
    def _start_container_sync(client: paramiko.SSHClient, container_id: str) -> bool:
        """
        Synchronously start a container using SSH client.
        """
        try:
            stdin, stdout, stderr = client.exec_command(f"docker start {container_id}")
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            if exit_status == 0:
                logger.info(f"Successfully started container {container_id}")
                return True
            else:
                logger.error(f"Failed to start container {container_id}. Error: {error}")
                return False
        except Exception as e:
            logger.error(f"Error starting container {container_id}: {e}")
            return False

    @staticmethod
    async def stop_container(db: AsyncSession, server_id: int, container_id: str) -> bool:
        """
        Stop a container on a server.
        """
        server = await ContainerControlService._get_server_by_id(db, server_id)
        if not server:
            logger.error(f"Server with ID {server_id} not found")
            return False

        try:
            client = await SSHConnectionService.get_ssh_client(server)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, ContainerControlService._stop_container_sync, client, container_id
            )
            client.close()
            return success
        except Exception as e:
            logger.error(f"Error stopping container {container_id} on server {server_id}: {e}")
            return False

    @staticmethod
    def _stop_container_sync(client: paramiko.SSHClient, container_id: str) -> bool:
        """
        Synchronously stop a container using SSH client.
        """
        try:
            stdin, stdout, stderr = client.exec_command(f"docker stop {container_id}")
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            if exit_status == 0:
                logger.info(f"Successfully stopped container {container_id}")
                return True
            else:
                logger.error(f"Failed to stop container {container_id}. Error: {error}")
                return False
        except Exception as e:
            logger.error(f"Error stopping container {container_id}: {e}")
            return False

    @staticmethod
    async def restart_container(db: AsyncSession, server_id: int, container_id: str) -> bool:
        """
        Restart a container on a server.
        """
        server = await ContainerControlService._get_server_by_id(db, server_id)
        if not server:
            logger.error(f"Server with ID {server_id} not found")
            return False

        try:
            client = await SSHConnectionService.get_ssh_client(server)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, ContainerControlService._restart_container_sync, client, container_id
            )
            client.close()
            return success
        except Exception as e:
            logger.error(f"Error restarting container {container_id} on server {server_id}: {e}")
            return False

    @staticmethod
    def _restart_container_sync(client: paramiko.SSHClient, container_id: str) -> bool:
        """
        Synchronously restart a container using SSH client.
        """
        try:
            stdin, stdout, stderr = client.exec_command(f"docker restart {container_id}")
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            if exit_status == 0:
                logger.info(f"Successfully restarted container {container_id}")
                return True
            else:
                logger.error(f"Failed to restart container {container_id}. Error: {error}")
                return False
        except Exception as e:
            logger.error(f"Error restarting container {container_id}: {e}")
            return False

    @staticmethod
    async def remove_container(
        db: AsyncSession, server_id: int, container_id: str, force: bool = False
    ) -> bool:
        """
        Remove a container on a server.
        """
        server = await ContainerControlService._get_server_by_id(db, server_id)
        if not server:
            logger.error(f"Server with ID {server_id} not found")
            return False

        try:
            client = await SSHConnectionService.get_ssh_client(server)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, ContainerControlService._remove_container_sync, client, container_id, force
            )
            client.close()
            return success
        except Exception as e:
            logger.error(f"Error removing container {container_id} on server {server_id}: {e}")
            return False

    @staticmethod
    def _remove_container_sync(
        client: paramiko.SSHClient, container_id: str, force: bool = False
    ) -> bool:
        """
        Synchronously remove a container using SSH client.
        """
        try:
            cmd = f"docker rm {'-f' if force else ''} {container_id}".strip()
            stdin, stdout, stderr = client.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            if exit_status == 0:
                logger.info(f"Successfully removed container {container_id}")
                return True
            else:
                logger.error(f"Failed to remove container {container_id}. Error: {error}")
                return False
        except Exception as e:
            logger.error(f"Error removing container {container_id}: {e}")
            return False

    @staticmethod
    async def get_container_by_id(
        db: AsyncSession, server_id: int, container_id: str
    ) -> Optional[ContainerSnapshot]:
        """
        Get container by ID from the latest snapshots for a server.
        """
        result = await db.execute(
            select(ContainerSnapshot)
            .where(ContainerSnapshot.server_id == server_id)
            .where(
                ContainerSnapshot.container_id.like(f"{container_id}%")
            )  # Allow partial ID match
        )

        # Return the first match (in case of partial ID match)
        containers = result.scalars().all()

        for container in containers:
            if container.container_id.startswith(container_id):
                return container

        return None

    @staticmethod
    def _get_container_logs_sync(
        client: paramiko.SSHClient,
        container_id: str,
        tail: int,
        timestamps: bool,
    ) -> list[str]:
        flags = "--timestamps" if timestamps else ""
        cmd = f"docker logs --tail {tail} {flags} {container_id} 2>&1"
        _, stdout, _ = client.exec_command(cmd)
        stdout.channel.recv_exit_status()
        raw = stdout.read().decode(errors="replace")
        return [line for line in raw.splitlines() if line]

    @staticmethod
    async def get_container_logs(
        db: AsyncSession,
        server_id: int,
        container_id: str,
        tail: int = 100,
        timestamps: bool = False,
    ) -> list[str]:
        server = await ContainerControlService._get_server_by_id(db, server_id)
        if not server:
            logger.error(f"Server with ID {server_id} not found")
            return []
        try:
            client = await SSHConnectionService.get_ssh_client(server)
            loop = asyncio.get_event_loop()
            lines = await loop.run_in_executor(
                None,
                ContainerControlService._get_container_logs_sync,
                client,
                container_id,
                tail,
                timestamps,
            )
            client.close()
            return lines
        except Exception as e:
            logger.error(f"Error fetching logs for container {container_id} on server {server_id}: {e}")
            return []

    @staticmethod
    async def _get_server_by_id(db: AsyncSession, server_id: int) -> Optional[Server]:
        """
        Helper to get server by ID.
        """
        result = await db.execute(select(Server).where(Server.id == server_id))
        return result.scalar_one_or_none()
