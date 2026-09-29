from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum

from sqlalchemy import and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.historical_metric import AggregationType, HistoricalMetric, MetricType
from app.models.server import Server

class TimeRange(str, Enum):
    LAST_HOUR = "1h"
    LAST_24_HOURS = "24h"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"

class HistoricalMetricService:

    @staticmethod
    async def save_aggregated_metric(
        db: AsyncSession,
        server_id: int,
        metric_type: MetricType,
        timestamp: datetime,
        value_min: Optional[float],
        value_max: Optional[float],
        value_avg: Optional[float],
        value_last: Optional[float],
        aggregation_level: AggregationType = AggregationType.MINUTE,
        sample_count: int = 1,
    ) -> HistoricalMetric:

        historical_metric = HistoricalMetric(
            server_id=server_id,
            metric_type=metric_type,
            aggregation_level=aggregation_level,
            timestamp=timestamp,
            period_start=timestamp,
            value_min=value_min,
            value_max=value_max,
            value_avg=value_avg,
            value_last=value_last,
            sample_count=sample_count,
        )

        db.add(historical_metric)
        await db.commit()
        await db.refresh(historical_metric)

        return historical_metric

    @staticmethod
    async def get_historical_metrics(
        db: AsyncSession,
        server_id: int,
        metric_type: MetricType,
        time_range: TimeRange,
        aggregation_level: AggregationType = AggregationType.MINUTE,
    ) -> List[HistoricalMetric]:

        now = datetime.utcnow()
        if time_range == TimeRange.LAST_HOUR:
            start_time = now - timedelta(hours=1)
        elif time_range == TimeRange.LAST_24_HOURS:
            start_time = now - timedelta(hours=24)
        elif time_range == TimeRange.LAST_7_DAYS:
            start_time = now - timedelta(days=7)
        elif time_range == TimeRange.LAST_30_DAYS:
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=1)

        query = (
            select(HistoricalMetric)
            .where(
                and_(
                    HistoricalMetric.server_id == server_id,
                    HistoricalMetric.metric_type == metric_type,
                    HistoricalMetric.aggregation_level == aggregation_level,
                    HistoricalMetric.timestamp >= start_time,
                )
            )
            .order_by(HistoricalMetric.timestamp.asc())
        )

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def aggregate_and_store_metrics(
        db: AsyncSession,
        server_id: int,
        metric_type: MetricType,
        start_time: datetime,
        end_time: datetime,
        aggregation_level: AggregationType,
    ) -> Optional[HistoricalMetric]:

        if aggregation_level == AggregationType.HOUR:
            window_size = timedelta(hours=1)
        elif aggregation_level == AggregationType.DAY:
            window_size = timedelta(days=1)
        else:
            window_size = timedelta(minutes=1)

        from app.models.metric import MetricSnapshot

        metric_column = HistoricalMetricService._get_raw_metric_column(metric_type)

        if not metric_column:
            return None

        raw_query = select(
            [
                func.min(metric_column).label("min_val"),
                func.max(metric_column).label("max_val"),
                func.avg(metric_column).label("avg_val"),
                func.count(metric_column).label("count_val"),
            ]
        ).where(
            and_(
                MetricSnapshot.server_id == server_id,
                metric_column.isnot(None),
                MetricSnapshot.collected_at >= start_time,
                MetricSnapshot.collected_at < end_time,
            )
        )

        result = await db.execute(raw_query)
        row = result.fetchone()

        if not row or row.count_val == 0:
            return None

        avg_value = float(row.avg_val) if row.avg_val is not None else None
        min_value = float(row.min_val) if row.min_val is not None else None
        max_value = float(row.max_val) if row.max_val is not None else None

        aggregated_metric = HistoricalMetric(
            server_id=server_id,
            metric_type=metric_type,
            aggregation_level=aggregation_level,
            timestamp=end_time,
            period_start=start_time,
            value_min=min_value,
            value_max=max_value,
            value_avg=avg_value,
            value_last=None,
            sample_count=int(row.count_val),
        )

        db.add(aggregated_metric)
        await db.commit()
        await db.refresh(aggregated_metric)

        return aggregated_metric

    @staticmethod
    def _get_raw_metric_column(metric_type: MetricType):

        from app.models.metric import MetricSnapshot

        column_map = {
            MetricType.CPU_PERCENT: MetricSnapshot.cpu_usage_percent,
            MetricType.MEMORY_PERCENT: MetricSnapshot.memory_usage_percent,
            MetricType.DISK_PERCENT: MetricSnapshot.disk_usage_percent,
            MetricType.LOAD_AVERAGE_1M: MetricSnapshot.load_average_1m,
            MetricType.LOAD_AVERAGE_5M: MetricSnapshot.load_average_5m,
            MetricType.LOAD_AVERAGE_15M: MetricSnapshot.load_average_15m,
            MetricType.NETWORK_IN: MetricSnapshot.network_in_bytes,
            MetricType.NETWORK_OUT: MetricSnapshot.network_out_bytes,
            MetricType.DISK_READ: MetricSnapshot.disk_read_bytes,
            MetricType.DISK_WRITE: MetricSnapshot.disk_write_bytes,
        }
        return column_map.get(metric_type)

    @staticmethod
    async def get_available_aggregation_levels(
        db: AsyncSession, server_id: int, metric_type: MetricType
    ) -> List[AggregationType]:

        query = (
            select(HistoricalMetric.aggregation_level)
            .where(
                and_(
                    HistoricalMetric.server_id == server_id,
                    HistoricalMetric.metric_type == metric_type,
                )
            )
            .distinct()
        )

        result = await db.execute(query)
        levels = [row[0] for row in result.all()]
        return [AggregationType(level) for level in levels]

    @staticmethod
    async def cleanup_old_raw_metrics(
        db: AsyncSession,
        retention_days: int = 7,
    ):

        from app.models.metric import MetricSnapshot

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        query = select(MetricSnapshot).where(MetricSnapshot.collected_at < cutoff_date)

        result = await db.execute(query)
        old_metrics = result.scalars().all()

        for metric in old_metrics:
            db.delete(metric)

        await db.commit()
