import asyncio
import datetime
import json
import logging
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

from data_gen.simulator.anomalies import AnomalyEngine, AnomalyType
from data_gen.simulator.config import SimulatorConfig
from data_gen.simulator.metrics import MetricsEngine, SimulatedMetrics
from data_gen.simulator.services import (
    ServicesState,
    create_services,
    tick_services,
)

logger = logging.getLogger(__name__)

MetricCallback = Callable[[SimulatedMetrics], None]
AnomalyCallback = Callable[[AnomalyType, str], None]

class SimulatorEngine:
    def __init__(self, config: SimulatorConfig) -> None:
        self.config = config
        self.services = create_services(config.services)
        self.metrics_engine = MetricsEngine(config)
        self.anomaly = AnomalyEngine(
            config,
            self.services,
            metrics_engine=self.metrics_engine,
            on_anomaly=self._on_anomaly,
        )
        self._metric_callbacks: List[MetricCallback] = []
        self._anomaly_callbacks: List[AnomalyCallback] = []
        self._latest_metrics: Optional[SimulatedMetrics] = None
        self._running = False
        self._tick_count = 0

    def on_metric(self, cb: MetricCallback) -> None:
        self._metric_callbacks.append(cb)

    def on_anomaly_event(self, cb: AnomalyCallback) -> None:
        self._anomaly_callbacks.append(cb)

    def _on_anomaly(self, anomaly_type: AnomalyType, started: bool) -> None:
        event_type = "start" if started else "end"
        logger.info(f"Anomaly event: {anomaly_type} {event_type}")
        for cb in self._anomaly_callbacks:
            try:
                cb(anomaly_type, event_type)
            except Exception as e:
                logger.error(f"Anomaly callback error: {e}")

    def latest_metrics(self) -> Optional[SimulatedMetrics]:
        return self._latest_metrics

    async def run(self) -> None:
        self._running = True
        interval = self.config.collection_interval_sec
        emit_interval = self.config.metrics_emit_interval_sec
        emit_counter = 0.0

        logger.info(
            f"Simulator started: {len(self.services.services)} services, "
            f"tick={interval}s, emit={emit_interval}s"
        )

        self.anomaly.start_auto()

        while self._running:
            loop_start = asyncio.get_event_loop().time()

            tick_services(self.services, self.config, dt=interval)
            metrics = self.metrics_engine.compute(
                self.services,
                dt=interval,
                anomaly_state=self.anomaly.state,
                anomaly_type=self.anomaly.current_type,
            )
            self._latest_metrics = metrics
            self._tick_count += 1
            emit_counter += interval

            if emit_counter >= emit_interval - 0.001:
                emit_counter = 0.0
                for cb in self._metric_callbacks:
                    try:
                        cb(metrics)
                    except Exception as e:
                        logger.error(f"Metric callback error: {e}")

            elapsed = asyncio.get_event_loop().time() - loop_start
            await asyncio.sleep(max(0.0, interval - elapsed))

    def stop(self) -> None:
        self._running = False
        self.anomaly.stop_auto()

class FileMetricExporter:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer: List[Dict] = []
        self._flush_interval = 100

    def __call__(self, metrics: SimulatedMetrics) -> None:
        d = {
            "timestamp": metrics.timestamp.isoformat(),
            "anomaly_active": metrics.anomaly_active,
            "anomaly_type": metrics.anomaly_type,
            "cpu_usage_percent": metrics.cpu_usage_percent,
            "cpu_per_core": metrics.cpu_per_core,
            "load_average_1m": metrics.load_average_1m,
            "load_average_5m": metrics.load_average_5m,
            "load_average_15m": metrics.load_average_15m,
            "memory_usage_percent": metrics.memory_usage_percent,
            "memory_used_mb": metrics.memory_used_mb,
            "memory_free_mb": metrics.memory_free_mb,
            "memory_cached_mb": metrics.memory_cached_mb,
            "swap_used_mb": metrics.swap_used_mb,
            "disk_usage_percent": metrics.disk_usage_percent,
            "disk_used_gb": metrics.disk_used_gb,
            "disk_free_gb": metrics.disk_free_gb,
            "network_in_bytes": metrics.network_in_bytes,
            "network_out_bytes": metrics.network_out_bytes,
            "disk_read_bytes": metrics.disk_read_bytes,
            "disk_write_bytes": metrics.disk_write_bytes,
            "uptime_seconds": metrics.uptime_seconds,
            "process_count": metrics.process_count,
            "active_connections": metrics.active_connections,
            "temperature_celsius": metrics.temperature_celsius,
            "container_count": metrics.container_count,
            "services_summary": metrics.services_summary,
            "containers": metrics.containers,
        }
        self._buffer.append(d)
        if len(self._buffer) >= self._flush_interval:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        with open(self.path, "a") as f:
            for item in self._buffer:
                f.write(json.dumps(item) + "\n")
        self._buffer.clear()

    def close(self) -> None:
        self.flush()
