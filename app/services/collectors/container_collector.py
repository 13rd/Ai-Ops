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

    @staticmethod
    async def collect_containers(server: Server) -> Optional[List[ContainerSnapshotBase]]:

        try:
            client = await SSHConnectionService.get_ssh_client(server)

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

        containers = []

        try:
            stdin, stdout, stderr = client.exec_command("which docker")
            docker_path = stdout.read().decode().strip()

            if not docker_path:
                logger.info("Docker not found on server")
                return []

            stdin, stdout, stderr = client.exec_command('docker ps -aq --format="{{.ID}}"')
            container_ids_output = stdout.read().decode().strip()

            if not container_ids_output:
                return []

            container_ids = container_ids_output.split("\n") if container_ids_output else []

            stdin, stdout, stderr = client.exec_command(
                'docker stats --no-stream --format="{{.ID}}|{{.CPUPerc}}|{{.MemUsage}}|{{.Status}}"'
            )
            stats_output = stdout.read().decode().strip()

            stats_dict = {}
            if stats_output:
                for line in stats_output.split("\n"):
                    if not line:
                        continue
                    try:
                        parts = line.split("|")
                        if len(parts) >= 4:
                            container_id = parts[0][:12]
                            cpu_perc_str = parts[1].replace("%", "").strip()
                            mem_usage = parts[2]
                            status = parts[3]

                            cpu_percentage = None
                            try:
                                cpu_percentage = float(cpu_perc_str)
                            except (ValueError, TypeError):
                                pass

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

            for cid in container_ids:
                if not cid.strip():
                    continue

                cmd = f"docker inspect {cid}"
                stdin, stdout, stderr = client.exec_command(cmd)
                inspect_output = stdout.read().decode().strip()

                try:
                    import json

                    container_info = json.loads(inspect_output)[0]

                    container_config = container_info.get("Config", {})
                    state_info = container_info.get("State", {})
                    network_settings = container_info.get("NetworkSettings", {})

                    container_id = container_info.get("Id", "")[:12]
                    container_name = container_info.get("Name", "").lstrip(
                        "/"
                    )
                    image = container_info.get("Config", {}).get("Image", "")

                    status = state_info.get("Status", "")

                    cpu_percentage = stats_dict.get(container_id, {}).get("cpu_percentage")
                    memory_usage_mb = stats_dict.get(container_id, {}).get("memory_usage_mb")

                    restart_count = state_info.get("RestartCount", 0)
                    health_status = state_info.get("Health", {}).get(
                        "Status", "unknown"
                    )

                    running = state_info.get("Running", False)

                    ports_parts = []
                    for port_proto, mappings in network_settings.get("Ports", {}).items():
                        if mappings:
                            ports_parts.append(port_proto)
                    ports = ", ".join(ports_parts)

                    command = container_config.get("Cmd", [])
                    if isinstance(command, list):
                        command = " ".join(command)

                    created_at = container_info.get("Created", "")
                    started_at = state_info.get("StartedAt", "")

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
                    try:
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

        try:
            mem_str = mem_str.upper().strip()

            import re

            num_match = re.search(r"([0-9.]+)", mem_str)
            if not num_match:
                return None

            num = float(num_match.group(1))

            if "KIB" in mem_str:
                return num / (1024 * 1024)
            elif "MIB" in mem_str:
                return num / 1024
            elif "GIB" in mem_str:
                return num * 1024
            elif "KB" in mem_str:
                return num / (1024 * 1024)
            elif "MB" in mem_str:
                return num
            elif "GB" in mem_str:
                return num * 1024
            elif "TB" in mem_str:
                return num * 1024 * 1024
            else:
                return num
        except:
            return None
