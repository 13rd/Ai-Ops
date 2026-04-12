import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.server import Server, ServerStatus
from app.services.collectors.container_collector import ContainerCollector
from app.services.collectors.metrics_collector import MetricsCollector
from app.services.collectors.snapshot_service import ContainerService, MetricService
from app.services.servers.server_service import ServerService

logger = logging.getLogger(__name__)


class CollectorScheduler:
    """
    Scheduler for periodic metrics and container collection.
    """

    def __init__(self):
        self.running = False
        self.task = None

    async def start(self):
        """
        Start the scheduler.
        """
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info("Collector scheduler started")

    async def stop(self):
        """
        Stop the scheduler.
        """
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
        """
        Main scheduler loop.
        """
        while self.running:
            try:
                await self._collect_all_servers()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")

            # Wait for next collection interval
            await asyncio.sleep(settings.METRICS_COLLECTION_INTERVAL)

    async def _collect_all_servers(self):
        """
        Collect metrics and containers from all servers.
        """
        async with AsyncSessionLocal() as db:
            try:
                # Get all servers
                servers = await ServerService.get_servers(db, skip=0, limit=10000)

                logger.info(f"Starting collection for {len(servers)} servers")

                # Collect from each server
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
        """
        Collect metrics and containers from a single server.
        """
        logger.info(f"Collecting data from server {server.id} ({server.name})")

        metrics_success = False
        containers_success = False

        # Collect metrics
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

        # Collect containers
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

        # Update server status
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


# Global scheduler instance
scheduler = CollectorScheduler()
