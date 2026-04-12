import asyncio
import logging
from datetime import datetime
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
    """
    Collector for system metrics from remote servers.
    Uses SSH to execute commands and parse output.
    """

    @staticmethod
    async def collect_metrics(server: Server) -> Optional[MetricSnapshotBase]:
        """
        Collect all system metrics from server.
        Returns MetricSnapshotBase or None if collection fails.
        """
        try:
            client = await SSHConnectionService.get_ssh_client(server)

            # Run collection in thread pool
            loop = asyncio.get_event_loop()
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
        """
        Synchronously collect metrics using SSH client.
        """
        metrics = MetricSnapshotBase()

        try:
            # CPU usage
            cpu_usage = MetricsCollector._get_cpu_usage(client)
            if cpu_usage is not None:
                metrics.cpu_usage_percent = cpu_usage

            # Load average
            load_avg = MetricsCollector._get_load_average(client)
            if load_avg:
                metrics.load_average_1m = load_avg.get("1m")
                metrics.load_average_5m = load_avg.get("5m")
                metrics.load_average_15m = load_avg.get("15m")

            # Memory
            memory = MetricsCollector._get_memory_info(client)
            if memory:
                metrics.memory_total_mb = memory.get("total")
                metrics.memory_used_mb = memory.get("used")
                metrics.memory_free_mb = memory.get("free")
                metrics.memory_usage_percent = memory.get("percent")

            # Disk
            disk = MetricsCollector._get_disk_info(client)
            if disk:
                metrics.disk_total_gb = disk.get("total")
                metrics.disk_used_gb = disk.get("used")
                metrics.disk_free_gb = disk.get("free")
                metrics.disk_usage_percent = disk.get("percent")

            # Network
            network = MetricsCollector._get_network_info(client)
            if network:
                metrics.network_in_bytes = network.get("in")
                metrics.network_out_bytes = network.get("out")

            # Uptime
            uptime = MetricsCollector._get_uptime(client)
            if uptime is not None:
                metrics.uptime_seconds = uptime

            # Disk I/O
            disk_io = MetricsCollector._get_disk_io_info(client)
            if disk_io:
                metrics.disk_read_bytes = disk_io.get("read_bytes")
                metrics.disk_write_bytes = disk_io.get("written_bytes")

            # Process count
            process_info = MetricsCollector._get_process_info(client)
            if process_info:
                metrics.process_count = process_info.get("total")

            # Active network connections
            try:
                netstat_output = MetricsCollector._execute_command(
                    client, "netstat -an | grep ESTABLISHED | wc -l"
                )
                metrics.active_connections = int(netstat_output)
            except Exception as e:
                logger.warning(f"Failed to get active connections: {e}")

        except Exception as e:
            logger.error(f"Error collecting specific metrics: {e}")

        return metrics

    @staticmethod
    def _execute_command(client: paramiko.SSHClient, command: str) -> str:
        """
        Execute command and return output.
        """
        stdin, stdout, stderr = client.exec_command(command)
        return stdout.read().decode().strip()

    @staticmethod
    def _get_cpu_usage(client: paramiko.SSHClient) -> Optional[float]:
        """
        Get CPU usage percentage.
        """
        try:
            # Use top command to get CPU usage
            output = MetricsCollector._execute_command(
                client,
                "top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'",
            )
            return float(output)
        except Exception as e:
            logger.warning(f"Failed to get CPU usage: {e}")
            return None

    @staticmethod
    def _get_load_average(client: paramiko.SSHClient) -> Optional[Dict[str, float]]:
        """
        Get load average (1m, 5m, 15m).
        """
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
        """
        Get memory information in MB.
        """
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
        """
        Get disk information in GB for root partition.
        """
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
        """
        Get network bytes in/out.
        """
        try:
            # Get network interfaces stats
            output = MetricsCollector._execute_command(
                client, "cat /proc/net/dev | grep -E 'eth[0-9]|ens[0-9]+|enp[0-9]+s[0-9]+'"
            )
            if not output:
                # Try to get at least some interface if specific patterns don't match
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
                            bytes_in = float(parts[1])  # RX bytes
                            bytes_out = float(parts[9])  # TX bytes
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
        """
        Get disk I/O statistics.
        """
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
                        # Skip RAM disks and partitions
                        device_name = parts[2]
                        if (
                            device_name.startswith("ram")
                            or "loop" in device_name
                            or device_name.startswith("sr")
                        ):
                            continue

                        # Read operations
                        reads_completed = int(parts[3])
                        sectors_read = int(parts[5])

                        # Write operations
                        writes_completed = int(parts[7])
                        sectors_written = int(parts[9])

                        total_reads += reads_completed
                        total_writes += writes_completed
                        total_read_bytes += (
                            sectors_read * 512
                        )  # Convert sectors to bytes (512 bytes per sector)
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
        """
        Get process count information.
        """
        try:
            # Get total number of processes
            total_processes = int(MetricsCollector._execute_command(client, "ps ax | wc -l"))
            # Subtract 1 for header line
            total_processes -= 1

            # Get number of running processes
            running_processes = int(MetricsCollector._execute_command(client, "ps r | wc -l"))
            running_processes -= 1  # Subtract 1 for header line

            return {
                "total": total_processes,
                "running": running_processes,
            }
        except Exception as e:
            logger.warning(f"Failed to get process info: {e}")
            return None

    @staticmethod
    def _get_uptime(client: paramiko.SSHClient) -> Optional[int]:
        """
        Get system uptime in seconds.
        """
        try:
            output = MetricsCollector._execute_command(
                client, "cat /proc/uptime | awk '{print $1}'"
            )
            return int(float(output))
        except Exception as e:
            logger.warning(f"Failed to get uptime: {e}")
            return None
