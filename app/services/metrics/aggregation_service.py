import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historical_metric import AggregationType, HistoricalMetric, MetricType
from app.models.metric import MetricSnapshot
from app.models.server import Server
from app.services.metrics.historical_service import HistoricalMetricService

logger = logging.getLogger(__name__)


class MetricsAggregationService:
    """
    Service to aggregate raw metrics into historical time-series data.
    Runs as a background service to periodically convert raw snapshots to aggregated data.
    """

    @staticmethod
    async def process_server_metrics(
        db: AsyncSession, server_id: int, cutoff_time: Optional[datetime] = None
    ):
        """
        Process raw metrics for a server and create aggregated historical data.
        """
        if cutoff_time is None:
            cutoff_time = datetime.utcnow() - timedelta(
                minutes=10
            )  # Process metrics older than 10 min

        # Get the latest aggregated timestamp for this server to avoid re-processing
        latest_hourly = await MetricsAggregationService._get_latest_aggregated_timestamp(
            db, server_id, AggregationType.HOUR
        )

        latest_daily = await MetricsAggregationService._get_latest_aggregated_timestamp(
            db, server_id, AggregationType.DAY
        )

        # Process hourly aggregation (if last processed more than 1 hour ago)
        if not latest_hourly or latest_hourly < (datetime.utcnow() - timedelta(hours=1)):
            await MetricsAggregationService._aggregate_to_hourly(db, server_id, latest_hourly)

        # Process daily aggregation (if last processed more than 1 day ago)
        if not latest_daily or latest_daily < (datetime.utcnow() - timedelta(days=1)):
            await MetricsAggregationService._aggregate_to_daily(db, server_id, latest_daily)

    @staticmethod
    async def _get_latest_aggregated_timestamp(
        db: AsyncSession, server_id: int, aggregation_level: AggregationType
    ) -> Optional[datetime]:
        """
        Get the latest timestamp of aggregated data for a server and aggregation level.
        """
        query = (
            select(HistoricalMetric.timestamp)
            .where(
                (HistoricalMetric.server_id == server_id)
                & (HistoricalMetric.aggregation_level == aggregation_level)
            )
            .order_by(HistoricalMetric.timestamp.desc())
            .limit(1)
        )

        result = await db.execute(query)
        latest = result.scalar_one_or_none()
        return latest

    @staticmethod
    async def _aggregate_to_hourly(
        db: AsyncSession, server_id: int, last_processed: Optional[datetime] = None
    ):
        """
        Aggregate minute-level metrics to hourly metrics.
        """
        if last_processed is None:
            # Start from the earliest raw metric if no previous aggregation exists
            raw_query = (
                select(MetricSnapshot.collected_at)
                .where(MetricSnapshot.server_id == server_id)
                .order_by(MetricSnapshot.collected_at.asc())
                .limit(1)
            )

            result = await db.execute(raw_query)
            first_metric = result.scalar_one_or_none()
            if first_metric:
                # Round down to the start of the hour
                last_processed = first_metric.replace(minute=0, second=0, microsecond=0)
            else:
                return

        # Process each hour since last aggregation
        current_hour = last_processed.replace(minute=0, second=0, microsecond=0)
        end_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

        while current_hour <= end_hour:
            next_hour = current_hour + timedelta(hours=1)

            # Process each metric type
            for metric_type in [
                MetricType.CPU_PERCENT,
                MetricType.MEMORY_PERCENT,
                MetricType.DISK_PERCENT,
                MetricType.LOAD_AVERAGE_1M,
                MetricType.NETWORK_IN,
                MetricType.NETWORK_OUT,
            ]:
                await HistoricalMetricService.aggregate_and_store_metrics(
                    db, server_id, metric_type, current_hour, next_hour, AggregationType.HOUR
                )

            current_hour = next_hour

    @staticmethod
    async def _aggregate_to_daily(
        db: AsyncSession, server_id: int, last_processed: Optional[datetime] = None
    ):
        """
        Aggregate hourly metrics to daily metrics.
        """
        if last_processed is None:
            # Start from the earliest hourly metric if no previous aggregation exists
            query = (
                select(HistoricalMetric.timestamp)
                .where(
                    (HistoricalMetric.server_id == server_id)
                    & (HistoricalMetric.aggregation_level == AggregationType.HOUR)
                )
                .order_by(HistoricalMetric.timestamp.asc())
                .limit(1)
            )

            result = await db.execute(query)
            first_metric = result.scalar_one_or_none()
            if first_metric:
                # Round down to the start of the day
                last_processed = first_metric.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                return

        # Process each day since last aggregation
        current_day = last_processed.replace(hour=0, minute=0, second=0, microsecond=0)
        end_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        while current_day <= end_day:
            next_day = current_day + timedelta(days=1)

            # Process each metric type (aggregate from hourly to daily)
            for metric_type in [
                MetricType.CPU_PERCENT,
                MetricType.MEMORY_PERCENT,
                MetricType.DISK_PERCENT,
                MetricType.LOAD_AVERAGE_1M,
                MetricType.NETWORK_IN,
                MetricType.NETWORK_OUT,
            ]:
                await MetricsAggregationService._aggregate_hourly_to_daily(
                    db, server_id, metric_type, current_day, next_day
                )

            current_day = next_day

    @staticmethod
    async def _aggregate_hourly_to_daily(
        db: AsyncSession,
        server_id: int,
        metric_type: MetricType,
        start_day: datetime,
        end_day: datetime,
    ):
        """
        Aggregate hourly historical metrics to daily.
        """
        # Get hourly metrics for the day range
        query = (
            select(HistoricalMetric)
            .where(
                (HistoricalMetric.server_id == server_id)
                & (HistoricalMetric.metric_type == metric_type)
                & (HistoricalMetric.aggregation_level == AggregationType.HOUR)
                & (HistoricalMetric.timestamp >= start_day)
                & (HistoricalMetric.timestamp < end_day)
            )
            .order_by(HistoricalMetric.timestamp.asc())
        )

        result = await db.execute(query)
        hourly_metrics = result.scalars().all()

        if not hourly_metrics:
            return

        # Calculate aggregates
        values = [h.value_avg for h in hourly_metrics if h.value_avg is not None]
        if not values:
            return

        min_val = min(values)
        max_val = max(values)
        avg_val = sum(values) / len(values)
        sample_count = sum(h.sample_count for h in hourly_metrics)

        # Store as daily aggregate
        daily_metric = HistoricalMetric(
            server_id=server_id,
            metric_type=metric_type,
            aggregation_level=AggregationType.DAY,
            timestamp=end_day,
            period_start=start_day,
            value_min=min_val,
            value_max=max_val,
            value_avg=avg_val,
            value_last=hourly_metrics[-1].value_last
            if hourly_metrics[-1].value_last is not None
            else None,
            sample_count=sample_count,
        )

        db.add(daily_metric)

    @staticmethod
    async def initialize_historical_metrics_from_raw(db: AsyncSession, server_id: int):
        """
        Initialize historical metrics from existing raw metrics.
        This is typically called when setting up historical storage for existing data.
        """
        # Get all raw metrics for the server
        raw_query = (
            select(MetricSnapshot)
            .where(MetricSnapshot.server_id == server_id)
            .order_by(MetricSnapshot.collected_at.asc())
        )

        result = await db.execute(raw_query)
        raw_metrics = result.scalars().all()

        # Group by metric type and create initial historical entries
        for metric_type in [
            MetricType.CPU_PERCENT,
            MetricType.MEMORY_PERCENT,
            MetricType.DISK_PERCENT,
            MetricType.LOAD_AVERAGE_1M,
            MetricType.NETWORK_IN,
            MetricType.NETWORK_OUT,
        ]:
            await MetricsAggregationService._create_initial_historical_from_raw(
                db, server_id, metric_type, raw_metrics
            )

    @staticmethod
    async def _create_initial_historical_from_raw(
        db: AsyncSession, server_id: int, metric_type: MetricType, raw_metrics: List[MetricSnapshot]
    ):
        """
        Create initial historical metrics from raw metrics for a specific metric type.
        """

        # Get the corresponding value from raw metric based on type
        def extract_value(metric: MetricSnapshot):
            mapping = {
                MetricType.CPU_PERCENT: metric.cpu_usage_percent,
                MetricType.MEMORY_PERCENT: metric.memory_usage_percent,
                MetricType.DISK_PERCENT: metric.disk_usage_percent,
                MetricType.LOAD_AVERAGE_1M: metric.load_average_1m,
                MetricType.NETWORK_IN: metric.network_in_bytes,
                MetricType.NETWORK_OUT: metric.network_out_bytes,
            }
            return mapping.get(metric_type)

        # Create minute-level historical metrics
        for raw_metric in raw_metrics:
            value = extract_value(raw_metric)
            if value is not None:
                # Round timestamp to nearest minute for aggregation
                rounded_timestamp = raw_metric.collected_at.replace(second=0, microsecond=0)

                historical_metric = HistoricalMetric(
                    server_id=server_id,
                    metric_type=metric_type,
                    aggregation_level=AggregationType.MINUTE,
                    timestamp=rounded_timestamp,
                    period_start=rounded_timestamp,
                    value_min=value,
                    value_max=value,
                    value_avg=value,
                    value_last=value,
                    sample_count=1,
                )

                db.add(historical_metric)

        await db.commit()
