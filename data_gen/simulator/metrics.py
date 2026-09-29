import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from data_gen.simulator.anomalies import AnomalyState
from data_gen.simulator.config import AnomalyType, SimulatorConfig
from data_gen.simulator.services import ServicesState, hour_of_week

@dataclass
class SimulatedMetrics:
    timestamp: datetime = field(default_factory=datetime.utcnow)
    anomaly_active: bool = False
    anomaly_type: Optional[str] = None
    cpu_usage_percent: float = 0.0
    cpu_per_core: List[float] = field(default_factory=list)
    load_average_1m: float = 0.0
    load_average_5m: float = 0.0
    load_average_15m: float = 0.0
    memory_total_mb: float = 0.0
    memory_used_mb: float = 0.0
    memory_free_mb: float = 0.0
    memory_usage_percent: float = 0.0
    memory_cached_mb: float = 0.0
    memory_buffered_mb: float = 0.0
    swap_total_mb: float = 0.0
    swap_used_mb: float = 0.0
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_free_gb: float = 0.0
    disk_usage_percent: float = 0.0
    network_in_bytes: float = 0.0
    network_out_bytes: float = 0.0
    disk_read_bytes: float = 0.0
    disk_write_bytes: float = 0.0
    uptime_seconds: int = 0
    process_count: int = 0
    active_connections: int = 0
    disk_io_await_ms: float = 0.0
    context_switches_per_sec: float = 0.0
    temperature_celsius: float = 45.0
    container_count: int = 0
    containers: List[Dict] = field(default_factory=list)
    services_summary: Dict = field(default_factory=dict)

class MetricsEngine:
    def __init__(self, config: SimulatorConfig) -> None:
        self.config = config
        self._uptime: float = random.uniform(3600 * 24 * 30, 3600 * 24 * 180)
        self._cpu_ema_1m: float = 30.0
        self._cpu_ema_5m: float = 30.0
        self._cpu_ema_15m: float = 30.0
        self._cpu_alpha_1m: float = 1 - math.exp(-1 / 60)
        self._cpu_alpha_5m: float = 1 - math.exp(-1 / 300)
        self._cpu_alpha_15m: float = 1 - math.exp(-1 / 900)
        self._disk_used_gb: float = random.uniform(
            config.server.disk_gb * 0.2,
            config.server.disk_gb * 0.5,
        )
        self._prev_cpu: float = 0.0
        self._prev_time: Optional[datetime] = None

    def compute(
        self,
        services: ServicesState,
        dt: float = 1.0,
        anomaly_state: AnomalyState = AnomalyState.IDLE,
        anomaly_type: Optional[AnomalyType] = None,
    ) -> SimulatedMetrics:
        now = datetime.utcnow()
        self._uptime += dt
        cfg = self.config.server

        total_cpu = sum(s.current_cpu_percent for s in services.services.values() if s.running)
        cpu_base = random.gauss(2.0, 0.5)
        total_cpu = min(95.0, max(0.5, total_cpu + cpu_base))
        total_cpu += random.uniform(-0.3, 0.3)

        per_core = []
        for core in range(cfg.cpu_cores):
            spread = random.gauss(0, total_cpu * 0.1)
            per_core.append(max(0.1, min(99.0, total_cpu + spread)))

        self._cpu_ema_1m += self._cpu_alpha_1m * (total_cpu - self._cpu_ema_1m)
        self._cpu_ema_5m += self._cpu_alpha_5m * (total_cpu - self._cpu_ema_5m)
        self._cpu_ema_15m += self._cpu_alpha_15m * (total_cpu - self._cpu_ema_15m)

        load_norm = total_cpu / 100
        load_1m = max(0.0, load_norm * cfg.cpu_cores * 0.85 + random.gauss(0, 0.05))
        load_5m = max(0.0, self._cpu_ema_5m / 100 * cfg.cpu_cores * 0.8 + random.gauss(0, 0.03))
        load_15m = max(0.0, self._cpu_ema_15m / 100 * cfg.cpu_cores * 0.75 + random.gauss(0, 0.02))

        mem_total_mb = cfg.memory_gb * 1024
        mem_used = sum(s.current_memory_mb for s in services.services.values())
        mem_os_overhead = random.gauss(cfg.memory_gb * 0.05 * 1024, 20)
        mem_cached = random.gauss(cfg.memory_gb * 0.15 * 1024, 50)
        mem_buffered = random.gauss(cfg.memory_gb * 0.03 * 1024, 10)
        mem_total_used = min(mem_total_mb * 0.95, mem_used + mem_os_overhead)
        mem_free = mem_total_mb - mem_total_used - mem_cached - mem_buffered
        mem_free = max(0, mem_free)
        mem_pct = (mem_total_used + mem_cached + mem_buffered) / mem_total_mb * 100

        swap_total_mb = cfg.swap_gb * 1024
        swap_used_mb = max(0, random.gauss(mem_total_mb * 0.02, 10))

        disk_total_gb = cfg.disk_gb
        disk_write_mb = sum(s.current_disk_write_kbps for s in services.services.values() if s.running) / 1024 * dt
        self._disk_used_gb += disk_write_mb / 1024
        self._disk_used_gb += random.gauss(0, 0.0001)
        self._disk_used_gb = max(1.0, min(disk_total_gb * 0.95, self._disk_used_gb))
        disk_free_gb = disk_total_gb - self._disk_used_gb
        disk_pct = self._disk_used_gb / disk_total_gb * 100

        net_in = sum(s.current_network_in_kbps for s in services.services.values() if s.running) * 1024 / 8
        net_out = sum(s.current_network_out_kbps for s in services.services.values() if s.running) * 1024 / 8

        disk_read = sum(s.current_disk_read_kbps for s in services.services.values() if s.running) * 1024 / 8
        disk_write = sum(s.current_disk_write_kbps for s in services.services.values() if s.running) * 1024 / 8

        proc_count = sum(
            p.instances * random.randint(3, 8)
            for p in self.config.services.values()
            if p.enabled
        ) + random.randint(50, 80)

        conn_count = sum(
            int(p.base_network_out_kbps / 50 * p.instances * random.uniform(0.8, 1.2))
            for p in self.config.services.values()
            if p.enabled
        ) + random.randint(5, 15)

        temp = 40.0 + total_cpu * 0.15 + random.gauss(0, 1.0)
        temp = min(85.0, max(35.0, temp))

        hw = hour_of_week()
        cron_likely = (
            (0 <= hw % 24 < 1 and hw // 24 < 5)
            or abs(hw % 24 - 3) < 0.5
        )
        if cron_likely and random.random() < 0.01:
            disk_read *= random.uniform(3, 10)
            disk_write *= random.uniform(2, 5)
            total_cpu += random.uniform(10, 30)

        container_list = []
        for name, svc in services.services.items():
            container_list.append({
                "name": f"sim-{name}",
                "image": f"simulated/{name}:latest",
                "status": "running" if svc.running else "stopped",
                "cpu_percent": round(svc.cpu_per_instance(), 2),
                "memory_mb": round(svc.current_memory_mb / max(svc.profile.instances, 1), 1),
                "restarts": svc.restarts,
                "health": svc.health,
            })

        services_summary = {
            name: {
                "running": svc.running,
                "cpu_percent": round(svc.current_cpu_percent, 2),
                "memory_mb": round(svc.current_memory_mb, 1),
                "instances": svc.profile.instances,
                "health": svc.health,
                "restarts": svc.restarts,
            }
            for name, svc in services.services.items()
        }

        return SimulatedMetrics(
            timestamp=now,
            anomaly_active=anomaly_state != AnomalyState.IDLE,
            anomaly_type=anomaly_type.value if anomaly_type else None,
            cpu_usage_percent=round(total_cpu, 2),
            cpu_per_core=[round(c, 2) for c in per_core],
            load_average_1m=round(load_1m, 2),
            load_average_5m=round(load_5m, 2),
            load_average_15m=round(load_15m, 2),
            memory_total_mb=round(mem_total_mb, 1),
            memory_used_mb=round(mem_total_used, 1),
            memory_free_mb=round(max(0, mem_free), 1),
            memory_usage_percent=round(mem_pct, 2),
            memory_cached_mb=round(mem_cached, 1),
            memory_buffered_mb=round(mem_buffered, 1),
            swap_total_mb=round(swap_total_mb, 1),
            swap_used_mb=round(swap_used_mb, 1),
            disk_total_gb=round(disk_total_gb, 1),
            disk_used_gb=round(self._disk_used_gb, 2),
            disk_free_gb=round(disk_free_gb, 2),
            disk_usage_percent=round(disk_pct, 2),
            network_in_bytes=int(net_in * dt),
            network_out_bytes=int(net_out * dt),
            disk_read_bytes=int(disk_read * dt),
            disk_write_bytes=int(disk_write * dt),
            uptime_seconds=int(self._uptime),
            process_count=int(proc_count),
            active_connections=int(conn_count),
            disk_io_await_ms=round(random.gauss(5, 2), 1),
            context_switches_per_sec=round(random.gauss(5000, 1000), 1),
            temperature_celsius=round(temp, 1),
            container_count=len(container_list),
            containers=container_list,
            services_summary=services_summary,
        )
