import asyncio
import logging
from typing import List, Optional

import paramiko

from app.models.server import Server
from app.schemas.container import ContainerSnapshotBase
from app.services.servers.connection_service import (
    ConnectionError,
    SSHConnectionService,
)

logger = logging.getLogger(__name__)


class ContainerCollector:
    """
    Collector for container information from remote servers.
    Focuses on Docker containers for Sprint 1.
    """

    @staticmethod
    async def collect_containers(server: Server) -> Optional[List[ContainerSnapshotBase]]:
        """
        Collect container information from server.
        Returns list of containers or None if collection fails.
        Returns empty list if Docker is not available.
        """
        try:
            client = await SSHConnectionService.get_ssh_client(server)

            # Run collection in thread pool
            loop = asyncio.get_event_loop()
            containers = await loop.run_in_executor(
                None,
                ContainerCollector._collect_containers_sync,
                client,
            )

            client.close()
            return containers

        except ConnectionError as e:
            logger.error(f"Connection error collecting containers from {server.host}: {e.message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error collecting containers from {server.host}: {e}")
            return None

    @staticmethod
    def _collect_containers_sync(client: paramiko.SSHClient) -> List[ContainerSnapshotBase]:
        """
        Synchronously collect container information using SSH client.
        """
        containers = []

        try:
            # Check if Docker is available
            stdin, stdout, stderr = client.exec_command("which docker")
            docker_path = stdout.read().decode().strip()

            if not docker_path:
                logger.info("Docker not found on server")
                return []

            # Get container list in JSON format
            stdin, stdout, stderr = client.exec_command(
                'docker ps -a --format "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}"'
            )
            output = stdout.read().decode().strip()

            if not output:
                return []

            # Parse container information
            for line in output.split("\n"):
                if not line:
                    continue

                try:
                    parts = line.split("|")
                    if len(parts) >= 4:
                        container = ContainerSnapshotBase(
                            container_id=parts[0],
                            container_name=parts[1],
                            image=parts[2],
                            status=parts[3],
                        )
                        containers.append(container)
                except Exception as e:
                    logger.warning(f"Failed to parse container line '{line}': {e}")
                    continue

        except Exception as e:
            logger.warning(f"Failed to collect containers: {e}")
            return []

        return containers
