import math
import random
from dataclasses import dataclass, field
from typing import Dict

from data_gen.simulator.config import ServiceProfile

@dataclass
class ServiceState:
    name: str
    profile: ServiceProfile
    current_cpu_percent: float = 0.0
    current_memory_mb: float = 0.0
    current_disk_read_kbps: float = 0.0
    current_disk_write_kbps: float = 0.0
    current_network_in_kbps: float = 0.0
    current_network_out_kbps: float = 0.0
    running: bool = True
    restarts: int = 0
    health: str = "healthy"

    def cpu_per_instance(self) -> float:
        return self.current_cpu_percent / max(self.profile.instances, 1)

@dataclass
class ServicesState:
    services: Dict[str, ServiceState] = field(default_factory=dict)

def create_services(profiles: Dict[str, ServiceProfile]) -> ServicesState:
    state = ServicesState()
    for name, profile in profiles.items():
        if profile.enabled:
            state.services[name] = ServiceState(name=name, profile=profile)
    return state

def hour_of_week() -> float:
    from datetime import datetime
    now = datetime.utcnow()
    return now.weekday() * 24 + now.hour + now.minute / 60 + now.second / 3600

def seasonality_multiplier(hw: float, config) -> float:
    daily_peak = config.daily_peak_hour
    weekly_peak = config.weekly_peak_day
    weekday = hw // 24
    hour = hw % 24

    is_weekend = weekday >= 5
    day_mult = config.weekend_multiplier if is_weekend else 1.0

    daily_cycle = math.sin(2 * math.pi * (hour - daily_peak + 6) / 24) * 0.5 + 0.5
    weekly_cycle = math.sin(2 * math.pi * (weekday - weekly_peak) / 7) * 0.15

    return day_mult * (config.amplitude * (0.5 + daily_cycle * 0.5 + weekly_cycle) + (1 - config.amplitude))

def tick_services(state: ServicesState, config, dt: float = 1.0) -> None:
    hw = hour_of_week()
    season = seasonality_multiplier(hw, config.seasonality)

    for svc in state.services.values():
        if not svc.running:
            svc.current_cpu_percent *= 0.95
            svc.current_memory_mb *= 0.99
            svc.current_disk_read_kbps *= 0.9
            svc.current_disk_write_kbps *= 0.9
            svc.current_network_in_kbps *= 0.9
            svc.current_network_out_kbps *= 0.9
            continue

        p = svc.profile
        base_cpu = p.base_cpu_percent * season * p.instances
        cpu_noise = random.gauss(0, p.cpu_noise_std * math.sqrt(p.instances))
        svc.current_cpu_percent = max(0.1, base_cpu + cpu_noise)

        base_mem = p.base_memory_mb * season * p.instances
        mem_noise = random.gauss(0, p.memory_noise_std * math.sqrt(p.instances))
        svc.current_memory_mb = max(1.0, base_mem + mem_noise)

        svc.current_disk_read_kbps = max(0, random.gauss(p.base_disk_read_kbps * p.instances * season, 100))
        svc.current_disk_write_kbps = max(0, random.gauss(p.base_disk_write_kbps * p.instances * season, 50))

        svc.current_network_in_kbps = max(0, random.gauss(p.base_network_in_kbps * p.instances * season, 200))
        svc.current_network_out_kbps = max(0, random.gauss(p.base_network_out_kbps * p.instances * season, 500))
