import logging
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from data_gen.simulator.anomalies import AnomalyState
from data_gen.simulator.config import AnomalyType, SimulatorConfig
from data_gen.simulator.engine import SimulatorEngine
from data_gen.simulator.metrics import SimulatedMetrics

logger = logging.getLogger(__name__)

class AnomalyRequest(BaseModel):
    type: AnomalyType
    duration_sec: int = 120
    params: Dict[str, Any] = {}

class ServiceOverride(BaseModel):
    running: Optional[bool] = None
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    health: Optional[str] = None

class ConfigUpdate(BaseModel):
    cpu_cores: Optional[int] = None
    memory_gb: Optional[float] = None
    disk_gb: Optional[float] = None
    daily_peak_hour: Optional[int] = None
    amplitude: Optional[float] = None
    noise_std: Optional[float] = None

def create_app(engine: SimulatorEngine) -> FastAPI:
    app = FastAPI(
        title="Server Simulator",
        description="Realistic server behavior simulator for anomaly detection training data",
        version="1.0.0",
    )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "anomaly_state": engine.anomaly.state.value,
            "current_anomaly": engine.anomaly.current_type.value if engine.anomaly.current_type else None,
            "tick_count": engine._tick_count,
        }

    @app.get("/metrics")
    async def get_metrics(format: str = Query("json", regex="^(json|prometheus)$")):
        m = engine.latest_metrics()
        if m is None:
            raise HTTPException(503, "No metrics yet")
        if format == "prometheus":
            return _to_prometheus(m)
        return _to_dict(m)

    @app.get("/metrics/latest")
    async def get_latest_metrics() -> Dict[str, Any]:
        m = engine.latest_metrics()
        if m is None:
            raise HTTPException(503, "No metrics yet")
        return _to_dict(m)

    @app.get("/services")
    async def list_services() -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "running": svc.running,
                "instances": svc.profile.instances,
                "cpu_percent": round(svc.current_cpu_percent, 2),
                "memory_mb": round(svc.current_memory_mb, 1),
                "health": svc.health,
                "restarts": svc.restarts,
            }
            for name, svc in engine.services.services.items()
        ]

    @app.post("/services/{name}/override")
    async def override_service(name: str, override: ServiceOverride):
        svc = engine.services.services.get(name)
        if svc is None:
            raise HTTPException(404, f"Service '{name}' not found")
        if override.running is not None:
            svc.running = override.running
        if override.cpu_percent is not None:
            svc.current_cpu_percent = override.cpu_percent
        if override.memory_mb is not None:
            svc.current_memory_mb = override.memory_mb
        if override.health is not None:
            svc.health = override.health
        return {"status": "ok", "service": name}

    @app.post("/anomaly/start")
    async def start_anomaly(req: AnomalyRequest):
        if engine.anomaly.state != AnomalyState.IDLE:
            raise HTTPException(
                409,
                f"Anomaly already running: {engine.anomaly.current_type}",
            )
        await engine.anomaly.start_anomaly(
            req.type,
            duration_sec=req.duration_sec,
            **req.params,
        )
        return {"status": "started", "type": req.type.value}

    @app.post("/anomaly/stop")
    async def stop_anomaly():
        if engine.anomaly.state == AnomalyState.IDLE:
            return {"status": "no_anomaly"}
        engine.anomaly.state = AnomalyState.IDLE
        engine.anomaly.current_type = None
        await engine.anomaly._cleanup(engine.anomaly.current_type or AnomalyType.CPU_SPIKE)
        return {"status": "stopped"}

    @app.get("/anomaly/status")
    async def anomaly_status() -> Dict[str, Any]:
        return {
            "state": engine.anomaly.state.value,
            "current_type": engine.anomaly.current_type.value if engine.anomaly.current_type else None,
            "auto_inject_enabled": engine.config.auto_anomaly.enabled,
        }

    @app.post("/anomaly/auto/toggle")
    async def toggle_auto_anomaly(enabled: bool = Query(...)):
        engine.config.auto_anomaly.enabled = enabled
        if enabled:
            engine.anomaly.start_auto()
        else:
            engine.anomaly.stop_auto()
        return {"auto_inject": enabled}

    @app.get("/config")
    async def get_config() -> Dict[str, Any]:
        cfg = engine.config
        return {
            "server": cfg.server.model_dump(),
            "seasonality": cfg.seasonality.model_dump(),
            "auto_anomaly": cfg.auto_anomaly.model_dump(),
            "collection_interval_sec": cfg.collection_interval_sec,
            "metrics_emit_interval_sec": cfg.metrics_emit_interval_sec,
        }

    @app.post("/config/update")
    async def update_config(update: ConfigUpdate) -> Dict[str, Any]:
        cfg = engine.config
        if update.cpu_cores is not None:
            cfg.server.cpu_cores = update.cpu_cores
        if update.memory_gb is not None:
            cfg.server.memory_gb = update.memory_gb
        if update.disk_gb is not None:
            cfg.server.disk_gb = update.disk_gb
        if update.daily_peak_hour is not None:
            cfg.seasonality.daily_peak_hour = update.daily_peak_hour
        if update.amplitude is not None:
            cfg.seasonality.amplitude = update.amplitude
        if update.noise_std is not None:
            cfg.seasonality.noise_std = update.noise_std
        return {"status": "ok", "config": get_config()}

    @app.get("/state/full")
    async def full_state() -> Dict[str, Any]:
        m = engine.latest_metrics()
        return {
            "timestamp": m.timestamp.isoformat() if m else None,
            "metrics": _to_dict(m) if m else None,
            "services": [
                {
                    "name": name,
                    "running": svc.running,
                    "instances": svc.profile.instances,
                    "cpu_percent": round(svc.current_cpu_percent, 2),
                    "memory_mb": round(svc.current_memory_mb, 1),
                    "health": svc.health,
                    "restarts": svc.restarts,
                }
                for name, svc in engine.services.services.items()
            ],
            "anomaly": {
                "state": engine.anomaly.state.value,
                "current_type": engine.anomaly.current_type.value if engine.anomaly.current_type else None,
            },
            "config": {
                "server": engine.config.server.model_dump(),
                "seasonality": engine.config.seasonality.model_dump(),
                "auto_anomaly": engine.config.auto_anomaly.model_dump(),
            },
        }

    return app

def _to_dict(m: SimulatedMetrics) -> Dict[str, Any]:
    return {
        "timestamp": m.timestamp.isoformat(),
        "cpu_usage_percent": m.cpu_usage_percent,
        "cpu_per_core": m.cpu_per_core,
        "load_average_1m": m.load_average_1m,
        "load_average_5m": m.load_average_5m,
        "load_average_15m": m.load_average_15m,
        "memory_total_mb": m.memory_total_mb,
        "memory_used_mb": m.memory_used_mb,
        "memory_free_mb": m.memory_free_mb,
        "memory_usage_percent": m.memory_usage_percent,
        "memory_cached_mb": m.memory_cached_mb,
        "memory_buffered_mb": m.memory_buffered_mb,
        "swap_total_mb": m.swap_total_mb,
        "swap_used_mb": m.swap_used_mb,
        "disk_total_gb": m.disk_total_gb,
        "disk_used_gb": m.disk_used_gb,
        "disk_free_gb": m.disk_free_gb,
        "disk_usage_percent": m.disk_usage_percent,
        "network_in_bytes": m.network_in_bytes,
        "network_out_bytes": m.network_out_bytes,
        "disk_read_bytes": m.disk_read_bytes,
        "disk_write_bytes": m.disk_write_bytes,
        "uptime_seconds": m.uptime_seconds,
        "process_count": m.process_count,
        "active_connections": m.active_connections,
        "disk_io_await_ms": m.disk_io_await_ms,
        "context_switches_per_sec": m.context_switches_per_sec,
        "temperature_celsius": m.temperature_celsius,
        "container_count": m.container_count,
        "containers": m.containers,
        "services_summary": m.services_summary,
    }

def _to_prometheus(m: SimulatedMetrics) -> str:
    ts = int(m.timestamp.timestamp() * 1000)
    lines = [
        f"# HELP simulator_cpu_usage_percent Current CPU usage percentage",
        f"# TYPE simulator_cpu_usage_percent gauge",
        f'simulator_cpu_usage_percent{ts} {m.cpu_usage_percent}',
        f"# HELP simulator_memory_usage_percent Current memory usage percentage",
        f"# TYPE simulator_memory_usage_percent gauge",
        f'simulator_memory_usage_percent{ts} {m.memory_usage_percent}',
        f"# HELP simulator_disk_usage_percent Current disk usage percentage",
        f"# TYPE simulator_disk_usage_percent gauge",
        f'simulator_disk_usage_percent{ts} {m.disk_usage_percent}',
        f"# HELP simulator_load_average_1m Load average 1 minute",
        f"# TYPE simulator_load_average_1m gauge",
        f'simulator_load_average_1m{ts} {m.load_average_1m}',
        f"# HELP simulator_active_connections Active network connections",
        f"# TYPE simulator_active_connections gauge",
        f'simulator_active_connections{ts} {m.active_connections}',
        f"# HELP simulator_temperature_celsius CPU temperature",
        f"# TYPE simulator_temperature_celsius gauge",
        f'simulator_temperature_celsius{ts} {m.temperature_celsius}',
        f"# HELP simulator_uptime_seconds System uptime",
        f"# TYPE simulator_uptime_seconds counter",
        f'simulator_uptime_seconds{ts} {m.uptime_seconds}',
    ]
    for i, core in enumerate(m.cpu_per_core):
        lines.append(
            f'simulator_cpu_per_core{{core="{i}"}}{ts} {core}'
        )
    for c in m.containers:
        lines.append(
            f'simulator_container_info{{name="{c["name"]}",status="{c["status"]}",health="{c["health"]}"}}{ts} 1'
        )
        lines.append(
            f'simulator_container_cpu_percent{{name="{c["name"]}"}}{ts} {c["cpu_percent"]}'
        )
        lines.append(
            f'simulator_container_memory_mb{{name="{c["name"]}"}}{ts} {c["memory_mb"]}'
        )
    return "\n".join(lines) + "\n"
