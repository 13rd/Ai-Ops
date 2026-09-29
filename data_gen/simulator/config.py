from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

class AnomalyType(str, Enum):
    CPU_SPIKE = "cpu_spike"
    MEMORY_LEAK = "memory_leak"
    SERVICE_DOWN = "service_down"
    CONTAINER_CRASH = "container_crash"
    DISK_FILL = "disk_fill"
    NETWORK_STORM = "network_storm"

class ServiceProfile(BaseModel):
    enabled: bool = True
    instances: int = 1
    base_cpu_percent: float = 5.0
    base_memory_mb: float = 256.0
    base_disk_read_kbps: float = 100.0
    base_disk_write_kbps: float = 50.0
    base_network_in_kbps: float = 10.0
    base_network_out_kbps: float = 50.0
    cpu_noise_std: float = 3.0
    memory_noise_std: float = 10.0
    seasonal_amplitude: float = 0.3

class SeasonalityConfig(BaseModel):
    daily_peak_hour: int = 14
    weekly_peak_day: int = 3
    amplitude: float = 0.4
    weekend_multiplier: float = 0.6
    noise_std: float = 2.0

class AutoAnomalyConfig(BaseModel):
    enabled: bool = False
    min_interval_minutes: int = 30
    max_interval_minutes: int = 90
    min_duration_minutes: int = 3
    max_duration_minutes: int = 12
    types: List[AnomalyType] = Field(default_factory=lambda: [t for t in AnomalyType])

class ServerConfig(BaseModel):
    name: str = "simulated-server"
    cpu_cores: int = 4
    memory_gb: float = 16.0
    disk_gb: float = 200.0
    swap_gb: float = 2.0

class SimulatorConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    services: Dict[str, ServiceProfile] = Field(default_factory=lambda: {
        "web": ServiceProfile(
            instances=4, base_cpu_percent=15.0, base_memory_mb=256.0,
            base_network_in_kbps=500.0, base_network_out_kbps=2000.0,
            seasonal_amplitude=0.5,
        ),
        "database": ServiceProfile(
            instances=1, base_cpu_percent=12.0, base_memory_mb=1024.0,
            base_disk_read_kbps=5000.0, base_disk_write_kbps=2000.0,
            seasonal_amplitude=0.4,
        ),
        "worker": ServiceProfile(
            instances=2, base_cpu_percent=8.0, base_memory_mb=512.0,
            cpu_noise_std=8.0, seasonal_amplitude=0.2,
        ),
        "cache": ServiceProfile(
            instances=1, base_cpu_percent=2.0, base_memory_mb=512.0,
            base_network_in_kbps=2000.0, base_network_out_kbps=1000.0,
            seasonal_amplitude=0.1,
        ),
    })
    seasonality: SeasonalityConfig = SeasonalityConfig()
    auto_anomaly: AutoAnomalyConfig = AutoAnomalyConfig()
    collection_interval_sec: float = 1.0
    metrics_emit_interval_sec: float = 15.0
    listen_host: str = "0.0.0.0"
    listen_port: int = 8100
