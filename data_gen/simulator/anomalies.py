import asyncio
import logging
import random
from enum import Enum
from typing import Callable, Dict, Optional

from data_gen.simulator.config import AnomalyType, SimulatorConfig
from data_gen.simulator.services import ServicesState

logger = logging.getLogger(__name__)

AnomalyCallback = Callable[[AnomalyType, bool], None]

class AnomalyState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    CLEANING = "cleaning"

class AnomalyEngine:
    def __init__(
        self,
        config: SimulatorConfig,
        services: ServicesState,
        metrics_engine=None,
        on_anomaly: Optional[AnomalyCallback] = None,
    ) -> None:
        self.config = config
        self.services = services
        self._metrics_engine = metrics_engine
        self.on_anomaly = on_anomaly
        self.state: AnomalyState = AnomalyState.IDLE
        self.current_type: Optional[AnomalyType] = None
        self._backup: Dict[str, Dict] = {}
        self._task: Optional[asyncio.Task] = None

    def _is_idle(self) -> bool:
        return all(s.running and s.health == "healthy" for s in self.services.services.values())

    def _save_backup(self) -> None:
        self._backup.clear()
        for name, svc in self.services.services.items():
            self._backup[name] = {
                "running": svc.running,
                "health": svc.health,
            }

    def _restore_backup(self) -> None:
        for name, backup in self._backup.items():
            if name in self.services.services:
                self.services.services[name].running = backup["running"]
                self.services.services[name].health = backup["health"]
        self._backup.clear()

    async def start_anomaly(
        self,
        anomaly_type: AnomalyType,
        duration_sec: int = 120,
        **kwargs,
    ) -> None:
        if self.state != AnomalyState.IDLE:
            raise RuntimeError(f"Anomaly already running: {self.current_type}")

        self.state = AnomalyState.RUNNING
        self.current_type = anomaly_type
        self._save_backup()

        logger.info(f"Starting anomaly: {anomaly_type} for {duration_sec}s")

        if self.on_anomaly:
            self.on_anomaly(anomaly_type, True)

        try:
            if anomaly_type == AnomalyType.CPU_SPIKE:
                await self._cpu_spike(duration_sec, **kwargs)
            elif anomaly_type == AnomalyType.MEMORY_LEAK:
                await self._memory_leak(duration_sec, **kwargs)
            elif anomaly_type == AnomalyType.SERVICE_DOWN:
                await self._service_down(duration_sec, **kwargs)
            elif anomaly_type == AnomalyType.CONTAINER_CRASH:
                await self._container_crash(duration_sec, **kwargs)
            elif anomaly_type == AnomalyType.DISK_FILL:
                await self._disk_fill(duration_sec, **kwargs)
            elif anomaly_type == AnomalyType.NETWORK_STORM:
                await self._network_storm(duration_sec, **kwargs)
        except Exception as e:
            logger.error(f"Anomaly {anomaly_type} failed: {e}")
        finally:
            self.state = AnomalyState.CLEANING
            await self._cleanup(anomaly_type)
            self.state = AnomalyState.IDLE
            self.current_type = None
            if self.on_anomaly:
                self.on_anomaly(anomaly_type, False)

    async def _cpu_spike(self, duration_sec: int, **kwargs) -> None:
        target_load = kwargs.get("target_load", 0.95)
        spike_duration = int(duration_sec * 0.6)
        aftermath = duration_sec - spike_duration

        logger.info(f"  Phase 1: CPU spike at {target_load*100:.0f}% for {spike_duration}s")
        for svc in self.services.services.values():
            if svc.running:
                svc.current_cpu_percent *= 3.0

        base_cpu = {
            n: s.current_cpu_percent
            for n, s in self.services.services.items()
        }

        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < spike_duration:
            for name, svc in self.services.services.items():
                if svc.running:
                    svc.current_cpu_percent = base_cpu[name] * random.uniform(2.5, 4.0)
                    svc.current_cpu_percent = min(99.0, max(30.0, svc.current_cpu_percent))
            await asyncio.sleep(2)

        logger.info(f"  Phase 2: Cooldown for {aftermath}s")
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < aftermath:
            progress = min(1.0, (asyncio.get_event_loop().time() - start) / aftermath)
            for name, svc in self.services.services.items():
                if svc.running:
                    target = base_cpu[name] * (0.8 + 1.2 * random.random())
                    svc.current_cpu_percent = base_cpu[name] * (1 - progress) + target * progress
                    svc.current_cpu_percent = max(1.0, svc.current_cpu_percent)
            await asyncio.sleep(2)

    async def _memory_leak(self, duration_sec: int, **kwargs) -> None:
        leak_duration = int(duration_sec * 0.75)
        peak_hold = duration_sec - leak_duration
        total_mem = self.config.server.memory_gb * 1024

        db_svc = self.services.services.get("database")
        if db_svc and db_svc.running:
            base_mem = db_svc.current_memory_mb
            max_leak_mem = total_mem * 0.92

            step = (max_leak_mem - base_mem) / (leak_duration / 1)
            logger.info(f"  Leaking memory: {base_mem:.0f}MB → {max_leak_mem:.0f}MB over {leak_duration}s")

            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < leak_duration:
                db_svc.current_memory_mb = min(max_leak_mem, db_svc.current_memory_mb + step * 2 * random.uniform(0.5, 1.5))
                await asyncio.sleep(1)

            logger.info(f"  Holding at peak for {peak_hold}s")
            await asyncio.sleep(peak_hold)

    async def _service_down(self, duration_sec: int, **kwargs) -> None:
        target_service = kwargs.get("target_service", "web")
        down_duration = int(duration_sec * 0.7)
        recovery = duration_sec - down_duration

        svc = self.services.services.get(target_service)
        if svc and svc.running:
            svc.running = False
            svc.health = "unreachable"
            logger.info(f"  Service '{target_service}' set to down for {down_duration}s")

            svc.current_cpu_percent = 0.1
            svc.current_memory_mb = svc.current_memory_mb * 0.3

            await asyncio.sleep(down_duration)

            svc.running = True
            svc.health = "degraded"
            logger.info(f"  Service '{target_service}' recovering for {recovery}s")

            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < recovery:
                await asyncio.sleep(2)

    async def _container_crash(self, duration_sec: int, **kwargs) -> None:
        target = kwargs.get("target_service", "worker")
        down_duration = int(duration_sec * 0.7)

        svc = self.services.services.get(target)
        if svc and svc.running:
            svc.running = False
            svc.health = "crashed"
            svc.restarts += 1
            logger.info(f"  Container '{target}' crashed, down for {down_duration}s")

            await asyncio.sleep(down_duration)

            svc.running = True
            svc.health = "recovering"
            logger.info(f"  Container '{target}' restarted")

            recovery_start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - recovery_start < duration_sec - down_duration:
                svc.current_cpu_percent = svc.profile.base_cpu_percent * random.uniform(0.8, 1.2)
                await asyncio.sleep(2)

    async def _disk_fill(self, duration_sec: int, **kwargs) -> None:
        fill_rate_gb_per_sec = kwargs.get("fill_rate_gb_per_sec", 0.05)
        max_fill_pct = kwargs.get("max_fill_pct", 0.95)
        total_disk = self.config.server.disk_gb
        max_fill = total_disk * max_fill_pct

        disk_attr = "_disk_used_gb"
        me = self._metrics_engine
        if me and hasattr(me, disk_attr):
            logger.info(f"  Filling disk to {max_fill:.0f}GB at ~{fill_rate_gb_per_sec}GB/s")
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < duration_sec:
                current = getattr(me, disk_attr)
                new_val = min(max_fill, current + fill_rate_gb_per_sec * random.uniform(0.8, 1.2))
                setattr(me, disk_attr, new_val)
                await asyncio.sleep(1)

    async def _network_storm(self, duration_sec: int, **kwargs) -> None:
        multiplier = kwargs.get("multiplier", 20)

        base_net = {
            n: (s.current_network_in_kbps, s.current_network_out_kbps)
            for n, s in self.services.services.items()
        }

        logger.info(f"  Network storm: {multiplier}x traffic for {duration_sec}s")
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < duration_sec:
            for name, svc in self.services.services.items():
                if svc.running:
                    base_in, base_out = base_net[name]
                    svc.current_network_in_kbps = base_in * multiplier * random.uniform(0.5, 1.5)
                    svc.current_network_out_kbps = base_out * multiplier * random.uniform(0.5, 1.5)
            await asyncio.sleep(2)

    async def _cleanup(self, anomaly_type: AnomalyType) -> None:
        logger.info(f"  Cleaning up after {anomaly_type}")
        self._restore_backup()

    async def auto_anomaly_loop(self) -> None:
        cfg = self.config.auto_anomaly
        if not cfg.enabled:
            return

        first_interval = random.randint(15, 45)

        while True:
            await asyncio.sleep(first_interval)
            first_interval = random.randint(
                cfg.min_interval_minutes * 60,
                cfg.max_interval_minutes * 60,
            )

            if self.state != AnomalyState.IDLE:
                continue

            anomaly_type = random.choice(cfg.types)
            duration = random.randint(
                cfg.min_duration_minutes * 60,
                cfg.max_duration_minutes * 60,
            )

            try:
                await self.start_anomaly(anomaly_type, duration)
            except Exception as e:
                logger.error(f"Auto anomaly failed: {e}")

    def start_auto(self) -> asyncio.Task:
        self._task = asyncio.create_task(self.auto_anomaly_loop())
        return self._task

    def stop_auto(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
