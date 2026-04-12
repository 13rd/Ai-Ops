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

            # Get detailed container information using docker inspect
            stdin, stdout, stderr = client.exec_command('docker ps -aq --format="{{.ID}}"')
            container_ids_output = stdout.read().decode().strip()

            if not container_ids_output:
                return []

            container_ids = container_ids_output.split("\n") if container_ids_output else []

            # Get container stats for running containers
            stdin, stdout, stderr = client.exec_command(
                'docker stats --no-stream --format="{{.ID}}|{{.CPUPerc}}|{{.MemUsage}}|{{.Status}}"'
            )
            stats_output = stdout.read().decode().strip()

            # Parse stats into a dictionary for easy lookup
            stats_dict = {}
            if stats_output:
                for line in stats_output.split("\n"):
                    if not line:
                        continue
                    try:
                        parts = line.split("|")
                        if len(parts) >= 4:
                            container_id = parts[0][:12]  # Docker uses first 12 chars as short ID
                            cpu_perc_str = parts[1].replace("%", "").strip()
                            mem_usage = parts[2]  # Format is "Used/Limit"
                            status = parts[3]

                            # Parse CPU percentage
                            cpu_percentage = None
                            try:
                                cpu_percentage = float(cpu_perc_str)
                            except (ValueError, TypeError):
                                pass

                            # Parse memory usage
                            mem_used_str = (
                                mem_usage.split("/")[0].strip() if "/" in mem_usage else mem_usage
                            )
                            mem_usage_mb = ContainerCollector._parse_memory_size(mem_used_str)

                            stats_dict[container_id] = {
                                "cpu_percentage": cpu_percentage,
                                "memory_usage_mb": mem_usage_mb,
                                "status": status,
                            }
                    except Exception as e:
                        logger.warning(f"Failed to parse stats line '{line}': {e}")
                        continue

            # Process each container
            for cid in container_ids:
                if not cid.strip():
                    continue

                # Get detailed container info
                cmd = f"docker inspect {cid}"
                stdin, stdout, stderr = client.exec_command(cmd)
                inspect_output = stdout.read().decode().strip()

                try:
                    import json

                    container_info = json.loads(inspect_output)[0]  # First container in array

                    # Extract container details
                    container_config = container_info.get("Config", {})
                    state_info = container_info.get("State", {})
                    network_settings = container_info.get("NetworkSettings", {})

                    # Basic info
                    container_id = container_info.get("Id", "")[:12]  # Short ID
                    container_name = container_info.get("Name", "").lstrip(
                        "/"
                    )  # Remove leading slash
                    image = container_info.get("Config", {}).get("Image", "")

                    # Extract status from docker ps or container state
                    status = state_info.get("Status", "")

                    # Default values that might be updated from stats
                    cpu_percentage = stats_dict.get(container_id, {}).get("cpu_percentage")
                    memory_usage_mb = stats_dict.get(container_id, {}).get("memory_usage_mb")

                    # Additional metrics
                    restart_count = state_info.get("RestartCount", 0)
                    health_status = state_info.get("Health", {}).get(
                        "Status", "unknown"
                    )  # health status

                    # Check if running from state
                    running = state_info.get("Running", False)

                    # Ports mapping
                    ports_parts = []
                    for port_proto, mappings in network_settings.get("Ports", {}).items():
                        if mappings:
                            ports_parts.append(port_proto)  # Just append the port/proto string
                    ports = ", ".join(ports_parts)

                    # Container command
                    command = container_config.get("Cmd", [])
                    if isinstance(command, list):
                        command = " ".join(command)

                    # Creation and start times
                    created_at = container_info.get("Created", "")
                    started_at = state_info.get("StartedAt", "")

                    # Memory percentage calculation (if possible)
                    memory_percentage = None
                    if memory_usage_mb is not None:
                        total_mem = container_info.get("HostConfig", {}).get("Memory", 0)
                        if total_mem > 0:
                            memory_percentage = (memory_usage_mb * 1024 * 1024 / total_mem) * 100

                    container = ContainerSnapshotBase(
                        container_id=container_id,
                        container_name=container_name,
                        image=image,
                        status=status,
                        cpu_percentage=cpu_percentage,
                        memory_usage_mb=memory_usage_mb,
                        memory_percentage=memory_percentage,
                        restart_count=restart_count,
                        health_status=health_status,
                        ports=ports,
                        command=command,
                        created_at=created_at,
                        started_at=started_at,
                        running=running,
                    )
                    containers.append(container)

                except Exception as e:
                    logger.warning(f"Failed to parse container details for {cid}: {e}")
                    # Fallback: just get basic info
                    try:
                        # Get basic info with docker ps
                        cmd = f'docker ps -a --filter "id={cid}" --format "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}"'
                        stdin, stdout, stderr = client.exec_command(cmd)
                        basic_output = stdout.read().decode().strip()

                        if basic_output:
                            parts = basic_output.split("|")
                            if len(parts) >= 4:
                                container = ContainerSnapshotBase(
                                    container_id=parts[0][:12],
                                    container_name=parts[1],
                                    image=parts[2],
                                    status=parts[3],
                                )
                                containers.append(container)
                    except:
                        continue

        except Exception as e:
            logger.warning(f"Failed to collect containers: {e}")
            return []

        return containers

    @staticmethod
    def _parse_memory_size(mem_str: str) -> Optional[float]:
        """
        Parse memory size string like '1.2GiB' or '512MiB' to MB.
        """
        try:
            mem_str = mem_str.upper().strip()

            # Remove MiB, GiB, etc. and extract numeric part
            import re

            num_match = re.search(r"([0-9.]+)", mem_str)
            if not num_match:
                return None

            num = float(num_match.group(1))

            # Extract unit
            if "KIB" in mem_str:
                return num / (1024 * 1024)  # KiB to MB
            elif "MIB" in mem_str:
                return num / 1024  # MiB to MB
            elif "GIB" in mem_str:
                return num * 1024  # GiB to MB
            elif "KB" in mem_str:
                return num / (1024 * 1024)  # KB to MB
            elif "MB" in mem_str:
                return num  # MB stays as MB
            elif "GB" in mem_str:
                return num * 1024  # GB to MB
            elif "TB" in mem_str:
                return num * 1024 * 1024  # TB to MB
            else:
                return num  # Assume bytes, convert to MB
        except:
            return None
