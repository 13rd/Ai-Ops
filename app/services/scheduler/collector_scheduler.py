import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.server import Server, ServerStatus
from app.services.alerts.alert_service import AlertEngine
from app.services.collectors.container_collector import ContainerCollector
from app.services.collectors.metrics_collector import MetricsCollector
from app.services.collectors.snapshot_service import ContainerService, MetricService
from app.services.servers.server_service import ServerService

logger = logging.getLogger(__name__)

class CollectorScheduler:

    def __init__(self):
        self.running = False
        self.task = None

    async def start(self):

        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info("Collector scheduler started")

    async def stop(self):

        if not self.running:
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("Collector scheduler stopped")

    async def _run(self):

        while self.running:
            try:
                await self._collect_all_servers()

                async with AsyncSessionLocal() as db:
                    try:
                        offline_alerts = await AlertEngine.check_offline_servers(db)
                        logger.info(
                            f"Offline server check completed, found {len(offline_alerts)} offline server alerts"
                        )
                    except Exception as e:
                        logger.error(f"Error during offline server checks: {e}")

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")

            await asyncio.sleep(settings.METRICS_INTERVAL_SEC)

    async def _collect_all_servers(self):

        async with AsyncSessionLocal() as db:
            try:
                all_servers = await ServerService.get_servers(db, skip=0, limit=10000)
                servers = [s for s in all_servers if s.ssh_username != "sim"]

                logger.info(
                    f"Starting collection for {len(servers)} servers "
                    f"({len(all_servers) - len(servers)} synthetic skipped)"
                )

                for server in servers:
                    try:
                        await self._collect_server_data(db, server)
                    except Exception as e:
                        logger.error(
                            f"Error collecting data from server {server.id} ({server.name}): {e}"
                        )

                logger.info("Collection cycle completed")

            except Exception as e:
                logger.error(f"Error getting servers list: {e}")

    async def _collect_server_data(self, db: AsyncSession, server: Server):

        logger.info(f"Collecting data from server {server.id} ({server.name})")

        metrics_success = False
        containers_success = False

        try:
            metrics = await MetricsCollector.collect_metrics(server)
            if metrics:
                await MetricService.save_metric_snapshot(db, server.id, metrics)
                metrics_success = True
                logger.info(f"Metrics collected successfully from {server.name}")
            else:
                logger.warning(f"Failed to collect metrics from {server.name}")
        except Exception as e:
            logger.error(f"Error collecting metrics from {server.name}: {e}")

        try:
            containers = await ContainerCollector.collect_containers(server)
            if containers is not None:
                await ContainerService.save_container_snapshots(db, server.id, containers)
                containers_success = True
                logger.info(
                    f"Containers collected successfully from {server.name} ({len(containers)} containers)"
                )
            else:
                logger.warning(f"Failed to collect containers from {server.name}")
        except Exception as e:
            logger.error(f"Error collecting containers from {server.name}: {e}")

        try:
            if metrics_success and containers_success:
                status = ServerStatus.ONLINE
            elif metrics_success or containers_success:
                status = ServerStatus.DEGRADED
            else:
                status = ServerStatus.OFFLINE

            await ServerService.update_server_status(db, server.id, status, datetime.utcnow())
            logger.info(f"Server {server.name} status updated to {status}")

        except Exception as e:
            logger.error(f"Error updating server status for {server.name}: {e}")

        try:
            await AlertEngine.evaluate_server_metrics(db, server)
            await AlertEngine.evaluate_containers(db, server)
            logger.info(f"Alert evaluation completed for server {server.name}")
        except Exception as e:
            logger.error(f"Error running alert evaluation for {server.name}: {e}")

scheduler = CollectorScheduler()
