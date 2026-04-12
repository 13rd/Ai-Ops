from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.container import ContainerSnapshot
from app.models.metric import MetricSnapshot
from app.models.server import Server
from app.schemas.container import ContainerSnapshotBase
from app.schemas.metric import MetricSnapshotBase


class MetricService:
    """
    Service for managing metric snapshots.
    """

    @staticmethod
    async def save_metric_snapshot(
        db: AsyncSession, server_id: int, metrics: MetricSnapshotBase
    ) -> MetricSnapshot:
        """
        Save metric snapshot to database.
        """
        snapshot = MetricSnapshot(
            server_id=server_id,
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
        )

        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)

        return snapshot

    @staticmethod
    async def get_latest_metrics(db: AsyncSession, server_id: int) -> Optional[MetricSnapshot]:
        """
        Get latest metric snapshot for server.
        """
        result = await db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.server_id == server_id)
            .order_by(MetricSnapshot.collected_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_metrics_history(
        db: AsyncSession, server_id: int, limit: int = 100
    ) -> List[MetricSnapshot]:
        """
        Get metric history for server.
        """
        result = await db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.server_id == server_id)
            .order_by(MetricSnapshot.collected_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class ContainerService:
    """
    Service for managing container snapshots.
    """

    @staticmethod
    async def save_container_snapshots(
        db: AsyncSession, server_id: int, containers: List[ContainerSnapshotBase]
    ) -> List[ContainerSnapshot]:
        """
        Save container snapshots to database.
        Replaces old snapshots for the server.
        """
        # Delete old snapshots for this server
        # TODO: Consider keeping history in Sprint 2+
        await db.execute(select(ContainerSnapshot).where(ContainerSnapshot.server_id == server_id))

        # Create new snapshots
        snapshots = []
        for container_data in containers:
            snapshot = ContainerSnapshot(
                server_id=server_id,
                container_id=container_data.container_id,
                container_name=container_data.container_name,
                image=container_data.image,
                status=container_data.status,
            )
            db.add(snapshot)
            snapshots.append(snapshot)

        await db.commit()

        return snapshots

    @staticmethod
    async def get_latest_containers(db: AsyncSession, server_id: int) -> List[ContainerSnapshot]:
        """
        Get latest container snapshots for server.
        """
        result = await db.execute(
            select(ContainerSnapshot)
            .where(ContainerSnapshot.server_id == server_id)
            .order_by(ContainerSnapshot.collected_at.desc())
        )

        # Group by container_id and get latest for each
        containers_dict = {}
        for container in result.scalars().all():
            if container.container_id not in containers_dict:
                containers_dict[container.container_id] = container

        return list(containers_dict.values())
