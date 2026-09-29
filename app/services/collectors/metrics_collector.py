import asyncio
import logging
from typing import Dict, Optional

import paramiko

from app.models.server import Server
from app.schemas.metric import MetricSnapshotBase
from app.services.servers.connection_service import (
    ConnectionError,
    SSHConnectionService,
)

logger = logging.getLogger(__name__)

class MetricsCollector:

    @staticmethod
    async def collect_metrics(server: Server) -> Optional[MetricSnapshotBase]:

        try:
            client = await SSHConnectionService.get_ssh_client(server)

            loop = asyncio.get_running_loop()
            metrics = await loop.run_in_executor(
                None,
                MetricsCollector._collect_metrics_sync,
                client,
            )

            client.close()
            return metrics

        except ConnectionError as e:
            logger.error(f"Connection error collecting metrics from {server.host}: {e.message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error collecting metrics from {server.host}: {e}")
            return None

    @staticmethod
    def _collect_metrics_sync(client: paramiko.SSHClient) -> MetricSnapshotBase:

        metrics = MetricSnapshotBase()

        try:
            cpu_usage = MetricsCollector._get_cpu_usage(client)
            if cpu_usage is not None:
                metrics.cpu_usage_percent = cpu_usage

            load_avg = MetricsCollector._get_load_average(client)
            if load_avg:
                metrics.load_average_1m = load_avg.get("1m")
                metrics.load_average_5m = load_avg.get("5m")
                metrics.load_average_15m = load_avg.get("15m")

            memory = MetricsCollector._get_memory_info(client)
            if memory:
                metrics.memory_total_mb = memory.get("total")
                metrics.memory_used_mb = memory.get("used")
                metrics.memory_free_mb = memory.get("free")
                metrics.memory_usage_percent = memory.get("percent")

            disk = MetricsCollector._get_disk_info(client)
            if disk:
                metrics.disk_total_gb = disk.get("total")
                metrics.disk_used_gb = disk.get("used")
                metrics.disk_free_gb = disk.get("free")
                metrics.disk_usage_percent = disk.get("percent")

            network = MetricsCollector._get_network_info(client)
            if network:
                metrics.network_in_bytes = network.get("in")
                metrics.network_out_bytes = network.get("out")

            uptime = MetricsCollector._get_uptime(client)
            if uptime is not None:
                metrics.uptime_seconds = uptime

            disk_io = MetricsCollector._get_disk_io_info(client)
            if disk_io:
                metrics.disk_read_bytes = disk_io.get("read_bytes")
                metrics.disk_write_bytes = disk_io.get("written_bytes")

            process_info = MetricsCollector._get_process_info(client)
            if process_info:
                metrics.process_count = process_info.get("total")

            try:
                netstat_output = MetricsCollector._execute_command(
                    client, "netstat -an | grep ESTABLISHED | wc -l"
                )
                metrics.active_connections = int(netstat_output)
            except Exception as e:
                logger.warning(f"Failed to get active connections: {e}")

            containers_ratio = MetricsCollector._get_containers_ratio(client)
            if containers_ratio >= 0:
                metrics.extra_data = metrics.extra_data or {}
                metrics.extra_data["containers_running_ratio"] = containers_ratio

        except Exception as e:
            logger.error(f"Error collecting specific metrics: {e}")

        return metrics

    @staticmethod
    def _execute_command(client: paramiko.SSHClient, command: str, timeout: int = 10) -> str:

        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        return stdout.read().decode().strip()

    @staticmethod
    def _get_cpu_usage(client: paramiko.SSHClient) -> Optional[float]:

        try:
            output = MetricsCollector._execute_command(
                client,
                "S1=$(grep '^cpu ' /proc/stat); sleep 0.5; S2=$(grep '^cpu ' /proc/stat); "
                "echo \"$S1|$S2\" | awk -F'|' '{n=split($1,a,\" \"); split($2,b,\" \"); "
                "i1=a[5];t1=0;for(k=2;k<=n;k++)t1+=a[k]; "
                "i2=b[5];t2=0;for(k=2;k<=n;k++)t2+=b[k]; "
                "dt=t2-t1; di=i2-i1; if(dt>0) printf \"%.1f\", 100*(dt-di)/dt; else printf \"0\"}'",
                timeout=15,
            )
            return float(output)
        except Exception as e:
            logger.warning(f"Failed to get CPU usage: {e}")
            return None

    @staticmethod
    def _get_load_average(client: paramiko.SSHClient) -> Optional[Dict[str, float]]:

        try:
            output = MetricsCollector._execute_command(client, "cat /proc/loadavg")
            parts = output.split()
            return {
                "1m": float(parts[0]),
                "5m": float(parts[1]),
                "15m": float(parts[2]),
            }
        except Exception as e:
            logger.warning(f"Failed to get load average: {e}")
            return None

    @staticmethod
    def _get_memory_info(client: paramiko.SSHClient) -> Optional[Dict[str, float]]:

        try:
            output = MetricsCollector._execute_command(client, "free -m | grep Mem")
            parts = output.split()
            total = float(parts[1])
            used = float(parts[2])
            free = float(parts[3])
            percent = (used / total) * 100 if total > 0 else 0

            return {
                "total": total,
                "used": used,
                "free": free,
                "percent": percent,
            }
        except Exception as e:
            logger.warning(f"Failed to get memory info: {e}")
            return None

    @staticmethod
    def _get_disk_info(client: paramiko.SSHClient) -> Optional[Dict[str, float]]:

        try:
            output = MetricsCollector._execute_command(client, "df -BG / | tail -1")
            parts = output.split()
            total = float(parts[1].replace("G", ""))
            used = float(parts[2].replace("G", ""))
            free = float(parts[3].replace("G", ""))
            percent = float(parts[4].replace("%", ""))

            return {
                "total": total,
                "used": used,
                "free": free,
                "percent": percent,
            }
        except Exception as e:
            logger.warning(f"Failed to get disk info: {e}")
            return None

    @staticmethod
    def _get_network_info(client: paramiko.SSHClient) -> Optional[Dict[str, float]]:

        try:
            output = MetricsCollector._execute_command(
                client, "cat /proc/net/dev | grep -E 'eth[0-9]|ens[0-9]+|enp[0-9]+s[0-9]+'"
            )
            if not output:
                output = MetricsCollector._execute_command(
                    client, "cat /proc/net/dev | grep -v -E 'Inter|face'"
                )

            lines = output.strip().split("\n")
            total_in = 0
            total_out = 0

            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 10:
                        try:
                            bytes_in = float(parts[1])
                            bytes_out = float(parts[9])
                            total_in += bytes_in
                            total_out += bytes_out
                        except (ValueError, IndexError):
                            continue

            if total_in > 0 or total_out > 0:
                return {
                    "in": total_in,
                    "out": total_out,
                }

            return None
        except Exception as e:
            logger.warning(f"Failed to get network info: {e}")
            return None

    @staticmethod
    def _get_disk_io_info(client: paramiko.SSHClient) -> Optional[Dict[str, float]]:

        try:
            output = MetricsCollector._execute_command(client, "cat /proc/diskstats")
            lines = output.strip().split("\n")

            total_reads = 0
            total_writes = 0
            total_read_bytes = 0
            total_written_bytes = 0

            for line in lines:
                parts = line.split()
                if len(parts) >= 14:
                    try:
                        device_name = parts[2]
                        if (
                            device_name.startswith("ram")
                            or "loop" in device_name
                            or device_name.startswith("sr")
                        ):
                            continue

                        reads_completed = int(parts[3])
                        sectors_read = int(parts[5])

                        writes_completed = int(parts[7])
                        sectors_written = int(parts[9])

                        total_reads += reads_completed
                        total_writes += writes_completed
                        total_read_bytes += (
                            sectors_read * 512
                        )
                        total_written_bytes += sectors_written * 512

                    except (ValueError, IndexError):
                        continue

            if total_reads > 0 or total_writes > 0:
                return {
                    "reads_completed": total_reads,
                    "writes_completed": total_writes,
                    "read_bytes": total_read_bytes,
                    "written_bytes": total_written_bytes,
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to get disk I/O info: {e}")
            return None

    @staticmethod
    def _get_process_info(client: paramiko.SSHClient) -> Optional[Dict[str, int]]:

        try:
            total_processes = int(MetricsCollector._execute_command(client, "ps ax | wc -l"))
            total_processes -= 1

            running_processes = int(MetricsCollector._execute_command(client, "ps r | wc -l"))
            running_processes -= 1

            return {
                "total": total_processes,
                "running": running_processes,
            }
        except Exception as e:
            logger.warning(f"Failed to get process info: {e}")
            return None

    @staticmethod
    def _get_uptime(client: paramiko.SSHClient) -> Optional[int]:

        try:
            output = MetricsCollector._execute_command(
                client, "cat /proc/uptime | awk '{print $1}'"
            )
            return int(float(output))
        except Exception as e:
            logger.warning(f"Failed to get uptime: {e}")
            return None

    @staticmethod
    def _get_containers_ratio(client: paramiko.SSHClient) -> float:

        try:
            total_out = MetricsCollector._execute_command(
                client, "docker ps -a --format '{{.Names}}' 2>/dev/null | wc -l"
            )
            running_out = MetricsCollector._execute_command(
                client, "docker ps --format '{{.Names}}' 2>/dev/null | wc -l"
            )
            total = int(total_out.strip())
            running = int(running_out.strip())
            if total == 0:
                return 1.0
            return running / total
        except Exception as e:
            logger.warning(f"Failed to get containers ratio: {e}")
            return -1.0
