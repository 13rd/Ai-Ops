import logging
import math
import random
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

from app.models.metric import MetricSnapshot
from data_gen.db import SessionLocal

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500

class ExpMovingAverage:
    def __init__(self, alpha: float):
        self.alpha = alpha
        self._value: Optional[float] = None

    def __call__(self, x: float) -> float:
        if self._value is None:
            self._value = x
        else:
            self._value = self.alpha * x + (1 - self.alpha) * self._value
        return self._value

class SyntheticNormalGenerator:
    def __init__(self, server_id: int) -> None:
        self.server_id = server_id
        self._uptime_hours: float = random.uniform(100, 2000)
        self._disk_used_gb: float = random.uniform(8, 20)
        self._proc_ema = ExpMovingAverage(0.3)
        self._cpu_ema = ExpMovingAverage(0.3)

    def _hour_of_week(self, ts: datetime) -> float:
        return ts.weekday() * 24 + ts.hour + ts.minute / 60

    def _cpu_target(self, hw: float) -> float:
        amplitude = 10 + 4 * math.sin(2 * math.pi * hw / 168)
        daily = (8 * math.sin(2 * math.pi * hw / 24)
                 + 3 * math.sin(2 * math.pi * hw / 12)
                 + 2 * math.sin(2 * math.pi * hw / 6))
        return max(5, 15 + amplitude + daily)

    def _cpu(self, t: float) -> float:
        target = self._cpu_target(t)
        noise = random.gauss(0, 3)
        raw = self._cpu_ema(target) + noise
        has_spike = random.random() < 0.001
        if has_spike:
            raw += random.uniform(20, 50)
        return max(1.0, min(95.0, raw))

    def _generate(self, interval_sec: int, total_rows: int, start_time: datetime) -> list:
        rows = []
        uptime = self._uptime_hours * 3600
        proc_base = random.randint(80, 120)

        for i in range(total_rows):
            ts = start_time + timedelta(seconds=i * interval_sec)
            uptime += interval_sec
            hw = self._hour_of_week(ts)

            cpu = self._cpu(hw)

            load_ema = self._proc_ema(cpu / 100)
            load_1m = max(0.0, load_ema * 4 + random.gauss(0, 0.15))
            load_5m = max(0.0, load_ema * 2.5 + random.gauss(0, 0.1))

            mem_gb = random.uniform(4, 16) if self.server_id >= 4 else 8
            total_mb = mem_gb * 1024
            ram_pct = max(20.0, min(80.0, random.gauss(42.0, 4.0)))
            used_mb = int(total_mb * ram_pct / 100)
            free_mb = total_mb - used_mb

            disk_drift = random.gauss(0.002, 0.01)
            disk_write = max(0, random.gauss(500_000, 300_000))
            self._disk_used_gb += disk_write / (1024**3) * interval_sec
            self._disk_used_gb += disk_drift
            self._disk_used_gb = max(2.0, self._disk_used_gb)
            disk_total = random.choice([50, 100, 200, 500])
            disk_used = min(self._disk_used_gb, disk_total * 0.95)
            disk_free = disk_total - disk_used
            disk_pct = round(disk_used / disk_total * 100, 2)

            net_in = max(0, random.gauss(200_000, 80_000) + cpu * 2000)
            net_out = max(0, random.gauss(100_000, 40_000) + cpu * 1000)

            disk_io = max(0, random.gauss(500_000, 200_000))
            has_cron = random.random() < 0.0005
            if has_cron:
                disk_io *= random.uniform(5, 20)

            proc_count = proc_base + int(cpu * 0.8) + random.randint(-5, 5)
            proc_count = max(10, min(300, proc_count))

            conn = max(0, int(random.gauss(15, 8) + cpu * 0.2))

            rows.append(MetricSnapshot(
                server_id=self.server_id,
                collected_at=ts,
                cpu_usage_percent=round(cpu, 2),
                load_average_1m=round(load_1m, 2),
                load_average_5m=round(load_5m, 2),
                load_average_15m=round(load_5m * 0.85 + random.gauss(0, 0.05), 2),
                memory_total_mb=total_mb,
                memory_used_mb=used_mb,
                memory_free_mb=free_mb,
                memory_usage_percent=round(ram_pct, 2),
                disk_total_gb=disk_total,
                disk_used_gb=round(disk_used, 2),
                disk_free_gb=round(disk_free, 2),
                disk_usage_percent=disk_pct,
                network_in_bytes=int(net_in),
                network_out_bytes=int(net_out),
                disk_read_bytes=int(disk_io * 0.6),
                disk_write_bytes=int(disk_io * 0.4),
                uptime_seconds=int(uptime),
                process_count=proc_count,
                active_connections=conn,
            ))

        return rows

    def generate(
        self,
        hours: int = 24,
        interval_sec: int = 15,
        start_time: Optional[datetime] = None,
    ) -> int:
        if start_time is None:
            start_time = datetime.utcnow() - timedelta(hours=hours)

        total_rows = int(hours * 3600 / interval_sec)
        rng_state = random.getstate()
        random.seed(self.server_id * 7919)

        rows = self._generate(interval_sec, total_rows, start_time)

        written = 0
        for i in range(0, len(rows), _BATCH_SIZE):
            batch = rows[i:i + _BATCH_SIZE]
            self._flush(batch)
            written += len(batch)

        random.setstate(rng_state)
        logger.info(
            f"[srv={self.server_id}] Synthetic normal data: {written} rows "
            f"({hours}h, interval={interval_sec}s)"
        )
        return written

    def _flush(self, batch: list) -> None:
        db = SessionLocal()
        try:
            db.bulk_save_objects(batch)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error(f"[srv={self.server_id}] DB flush failed: {exc}")
        finally:
            db.close()
