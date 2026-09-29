import logging
import threading
import time
from datetime import datetime
from typing import Optional

import paramiko

from app.models.container import ContainerSnapshot
from app.models.metric import MetricSnapshot
from app.services.collectors.container_collector import ContainerCollector
from app.services.collectors.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

class SSHCollector:

    def __init__(
        self,
        server_id: int,
        host: str,
        port: int,
        username: str,
        db_session_factory,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        interval: int = 15,
    ) -> None:
        self.server_id = server_id
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.db_session_factory = db_session_factory
        self.interval = interval
        self._stop_event = threading.Event()

    def _make_client(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: dict = {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "timeout": 10,
            "look_for_keys": False,
            "allow_agent": False,
        }
        if self.password:
            kwargs["password"] = self.password
        elif self.private_key:
            from io import StringIO
            kwargs["pkey"] = paramiko.RSAKey.from_private_key(StringIO(self.private_key))
        client.connect(**kwargs)
        return client

    @staticmethod
    def _running_ratio(containers) -> float:

        items = containers or []
        if not items:
            return 1.0
        running = 0
        for c in items:
            status = (getattr(c, "status", "") or "").lower()
            if status.startswith("up") or "running" in status or "healthy" in status:
                running += 1
        return running / len(items)

    def _collect_once(self) -> None:
        try:
            client = self._make_client()
            metrics = MetricsCollector._collect_metrics_sync(client)
            containers = ContainerCollector._collect_containers_sync(client)
            client.close()
        except Exception as exc:
            logger.error(f"[srv={self.server_id}] SSH collection failed: {exc}")
            return

        running_ratio = self._running_ratio(containers)

        db = self.db_session_factory()
        try:
            now = datetime.utcnow()
            snapshot = MetricSnapshot(
                server_id=self.server_id,
                collected_at=now,
                extra_data={
                    "containers_running_ratio": running_ratio,
                    "swap_used_mb": getattr(metrics, "swap_used_mb", 0.0) or 0.0,
                },
                cpu_usage_percent=metrics.cpu_usage_percent,
                load_average_1m=metrics.load_average_1m,
                load_average_5m=metrics.load_average_5m,
                load_average_15m=metrics.load_average_15m,
                memory_total_mb=metrics.memory_total_mb,
                memory_used_mb=metrics.memory_used_mb,
                memory_free_mb=metrics.memory_free_mb,
                memory_usage_percent=metrics.memory_usage_percent,
                disk_total_gb=metrics.disk_total_gb,
                disk_used_gb=metrics.disk_used_gb,
                disk_free_gb=metrics.disk_free_gb,
                disk_usage_percent=metrics.disk_usage_percent,
                network_in_bytes=metrics.network_in_bytes,
                network_out_bytes=metrics.network_out_bytes,
                uptime_seconds=metrics.uptime_seconds,
                disk_read_bytes=metrics.disk_read_bytes,
                disk_write_bytes=metrics.disk_write_bytes,
                process_count=metrics.process_count,
                active_connections=metrics.active_connections,
            )
            db.add(snapshot)

            db.query(ContainerSnapshot).filter(
                ContainerSnapshot.server_id == self.server_id
            ).delete()
            for c in containers or []:
                db.add(
                    ContainerSnapshot(
                        server_id=self.server_id,
                        container_id=c.container_id,
                        container_name=c.container_name,
                        image=c.image,
                        status=c.status,
                        collected_at=now,
                        extra_data={
                            "cpu_percentage": c.cpu_percentage,
                            "memory_usage_mb": c.memory_usage_mb,
                            "memory_percentage": c.memory_percentage,
                            "restart_count": c.restart_count,
                            "health_status": c.health_status,
                        },
                    )
                )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error(f"[srv={self.server_id}] DB write failed: {exc}")
        finally:
            db.close()

    def run(self) -> None:
        logger.info(f"Collector started: server_id={self.server_id} host={self.host}")
        while not self._stop_event.is_set():
            start = time.monotonic()
            self._collect_once()
            elapsed = time.monotonic() - start
            self._stop_event.wait(timeout=max(0.0, self.interval - elapsed))

    def stop(self) -> None:
        self._stop_event.set()
