from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.container import ContainerSnapshot
from app.models.historical_metric import AggregationType, HistoricalMetric, MetricType
from app.models.metric import MetricSnapshot
from app.models.server import Server
from app.schemas.container import ContainerSnapshotBase
from app.schemas.metric import MetricSnapshotBase

class MetricService:

    @staticmethod
    async def save_metric_snapshot(
        db: AsyncSession, server_id: int, metrics: MetricSnapshotBase
    ) -> MetricSnapshot:

        extra_data: dict = {}
        if metrics.extra_data:
            extra_data.update(metrics.extra_data)
        if metrics.process_count is not None:
            extra_data["process_count"] = metrics.process_count

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
            disk_read_bytes=metrics.disk_read_bytes,
            disk_write_bytes=metrics.disk_write_bytes,
            process_count=metrics.process_count,
            active_connections=metrics.active_connections,
            extra_data=extra_data,
        )

        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)

        await MetricService._update_historical_metrics(
            db, server_id, metrics, snapshot.collected_at
        )

        return snapshot

    @staticmethod
    async def _update_historical_metrics(
        db: AsyncSession, server_id: int, metrics: MetricSnapshotBase, timestamp: datetime
    ):

        from app.services.metrics.historical_service import HistoricalMetricService

        minute_timestamp = timestamp.replace(second=0, microsecond=0)

        metric_updates = [
            (MetricType.CPU_PERCENT, metrics.cpu_usage_percent),
            (MetricType.MEMORY_PERCENT, metrics.memory_usage_percent),
            (MetricType.DISK_PERCENT, metrics.disk_usage_percent),
            (MetricType.LOAD_AVERAGE_1M, metrics.load_average_1m),
            (MetricType.NETWORK_IN, metrics.network_in_bytes),
            (MetricType.NETWORK_OUT, metrics.network_out_bytes),
            (MetricType.DISK_READ, metrics.disk_read_bytes),
            (MetricType.DISK_WRITE, metrics.disk_write_bytes),
        ]

        for metric_type, value in metric_updates:
            if value is not None:
                await MetricService._save_minute_metric(
                    db, server_id, metric_type, value, minute_timestamp
                )

    @staticmethod
    async def _save_minute_metric(
        db: AsyncSession, server_id: int, metric_type: MetricType, value: float, timestamp: datetime
    ):

        from app.services.metrics.historical_service import HistoricalMetricService

        query = (
            select(HistoricalMetric)
            .where(
                (HistoricalMetric.server_id == server_id)
                & (HistoricalMetric.metric_type == metric_type)
                & (HistoricalMetric.aggregation_level == AggregationType.MINUTE)
                & (HistoricalMetric.timestamp == timestamp)
            )
            .order_by(HistoricalMetric.id.desc())
            .limit(1)
        )

        result = await db.execute(query)
        existing_metric = result.scalar_one_or_none()

        if existing_metric:
            if existing_metric.value_min is None or value < existing_metric.value_min:
                existing_metric.value_min = value
            if existing_metric.value_max is None or value > existing_metric.value_max:
                existing_metric.value_max = value

            total_samples = existing_metric.sample_count + 1
            total_sum = (existing_metric.value_avg * existing_metric.sample_count) + value
            existing_metric.value_avg = total_sum / total_samples

            existing_metric.value_last = value
            existing_metric.sample_count += 1
        else:
            new_metric = HistoricalMetric(
                server_id=server_id,
                metric_type=metric_type,
                aggregation_level=AggregationType.MINUTE,
                timestamp=timestamp,
                period_start=timestamp,
                value_min=value,
                value_max=value,
                value_avg=value,
                value_last=value,
                sample_count=1,
            )
            db.add(new_metric)

        await db.commit()

    @staticmethod
    async def get_latest_metrics(db: AsyncSession, server_id: int) -> Optional[MetricSnapshot]:

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

        result = await db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.server_id == server_id)
            .order_by(MetricSnapshot.collected_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

class ContainerService:

    @staticmethod
    async def save_container_snapshots(
        db: AsyncSession, server_id: int, containers: List[ContainerSnapshotBase]
    ) -> List[ContainerSnapshot]:

        from sqlalchemy import delete

        await db.execute(delete(ContainerSnapshot).where(ContainerSnapshot.server_id == server_id))

        snapshots = []
        for container_data in containers:
            snapshot = ContainerSnapshot(
                server_id=server_id,
                container_id=container_data.container_id,
                container_name=container_data.container_name,
                image=container_data.image,
                status=container_data.status,
                extra_data={
                    "cpu_percentage": container_data.cpu_percentage,
                    "memory_usage_mb": container_data.memory_usage_mb,
                    "memory_percentage": container_data.memory_percentage,
                    "restart_count": container_data.restart_count,
                    "health_status": container_data.health_status,
                    "ports": container_data.ports,
                    "command": container_data.command,
                    "created_at": container_data.created_at,
                    "started_at": container_data.started_at,
                    "running": container_data.running,
                },
            )
            db.add(snapshot)
            snapshots.append(snapshot)

        await db.commit()

        return snapshots

    @staticmethod
    async def get_latest_containers(db: AsyncSession, server_id: int) -> List[ContainerSnapshot]:

        result = await db.execute(
            select(ContainerSnapshot)
            .where(ContainerSnapshot.server_id == server_id)
            .order_by(ContainerSnapshot.collected_at.desc())
        )

        containers_dict = {}
        for container in result.scalars().all():
            if container.container_id not in containers_dict:
                containers_dict[container.container_id] = container

        return list(containers_dict.values())
