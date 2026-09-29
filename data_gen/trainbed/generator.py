import logging
import math
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

_TRAINBED_DB_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://trainbed:trainbed@postgres:5432/trainbed")
os.environ["DATABASE_URL"] = _TRAINBED_DB_URL.replace("+psycopg2", "+asyncpg")

from app.db.base import Base
from app.models.anomaly_event import AnomalyEvent
from app.models.container import ContainerSnapshot
from app.models.metric import MetricSnapshot
from app.models.server import Server

from data_gen.trainbed.profiles import Profile, PROFILES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("trainbed")

INTERVAL_SEC = 15

_CANONICAL_SCENARIO: dict[str, str] = {
    "disk_pressure": "disk_fill",
    "network_anomaly": "network_storm",
}

class ExpMovingAverage:
    def __init__(self, alpha: float, initial: float = 0.0):
        self.alpha = alpha
        self._value = initial

    def __call__(self, x: float) -> float:
        self._value = self.alpha * x + (1 - self.alpha) * self._value
        return self._value

CONTAINER_CONFIG: dict[str, tuple[str, str]] = {
    "web_server":     ("web-nginx",     "nginx:alpine"),
    "database":       ("db-postgres",   "postgres:16-alpine"),
    "file_storage":   ("fs-samba",      "samba:latest"),
    "worker":         ("wk-runner",     "python:3.11-slim"),
    "monitoring":     ("mon-prometheus","prom/prometheus:latest"),
    "load_balancer":  ("lb-haproxy",    "haproxy:lts-alpine"),
}

class GeneratorState:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.uptime_sec = profile.uptime_hours * 3600
        self.disk_used_gb = profile.disk_total_gb * random.uniform(0.08, 0.25)
        self.cpu_ema = ExpMovingAverage(0.3, profile.cpu_base)
        self.proc_ema = ExpMovingAverage(0.3, profile.proc_base)
        self.container_status = "running"

        self.mode: str = "normal"
        self.current_anomaly: Optional[str] = None
        self.event_id: Optional[int] = None
        self.anomaly_start: Optional[datetime] = None
        self.anomaly_end: Optional[datetime] = None
        self.schedule_idx = 0

        self.leak_allocated_mb: float = 0
        self.total_ram_mb: float = 0

    def hour_of_week(self, ts: datetime) -> float:
        return ts.weekday() * 24 + ts.hour + ts.minute / 60

def _sine(hw: float, period: float) -> float:
    return math.sin(2 * math.pi * hw / period)

def _first_ts(session: Session, server_id: int) -> datetime:
    row = (
        session.query(MetricSnapshot)
        .filter(MetricSnapshot.server_id == server_id)
        .order_by(MetricSnapshot.collected_at.asc())
        .first()
    )
    return row.collected_at if row else datetime.utcnow()

def _pick_total_ram(p: Profile) -> float:
    return {10: 8192, 11: 16384, 12: 4096, 13: 8192, 14: 4096, 15: 8192}.get(p.server_id, 8192)

def _start_anomaly(state: GeneratorState, ts: datetime, session: Session) -> None:
    p = state.profile
    atype = p.anomaly_types[state.schedule_idx % len(p.anomaly_types)]
    duration_min = {
        "cpu_spike": 8,
        "memory_leak": 20,
        "container_crash": 10,
        "service_down": 12,
        "disk_pressure": 25,
        "network_anomaly": 10,
    }[atype]

    logger.info("[srv=%d] START anomaly=%s duration=%dmin", p.server_id, atype, duration_min)

    state.mode = "anomaly"
    state.current_anomaly = atype
    state.anomaly_start = ts
    state.anomaly_end = ts + timedelta(minutes=duration_min)

    if atype == "memory_leak":
        state.total_ram_mb = _pick_total_ram(p)
        state.leak_allocated_mb = state.total_ram_mb * 0.25
    elif atype == "container_crash":
        state.container_status = "stopped"

    event = AnomalyEvent(
        server_id=p.server_id,
        scenario_type=_CANONICAL_SCENARIO.get(atype, atype),
        start_ts=ts,
        end_ts=None,
        parameters={"scheduled": True, "duration_min": duration_min},
    )
    session.add(event)
    session.flush()
    state.event_id = event.id
    session.commit()

    state.schedule_idx += 1

def _end_anomaly(state: GeneratorState, ts: datetime, session: Session) -> None:
    p = state.profile
    logger.info("[srv=%d] END anomaly=%s", p.server_id, state.current_anomaly)

    if state.event_id:
        event = session.get(AnomalyEvent, state.event_id)
        if event:
            event.end_ts = ts
            session.commit()

    state.mode = "normal"
    state.current_anomaly = None
    state.event_id = None
    state.anomaly_start = None
    state.anomaly_end = None
    state.container_status = "running"

    if state.schedule_idx >= len(p.anomaly_schedule_min):
        state.schedule_idx = 0

def _gen_cpu(state: GeneratorState, hw: float) -> float:
    p = state.profile
    if state.mode == "normal":
        target = p.cpu_base + p.cpu_amplitude * (
            0.6 * _sine(hw, 24) + 0.25 * _sine(hw, 12) + 0.15 * _sine(hw, 8)
        )
        noise = random.gauss(0, p.cpu_noise)
        burst = random.random() < p.cpu_burst_prob
        return max(1.0, min(95.0, state.cpu_ema(target) + noise + (burst * p.cpu_burst_mag)))
    elif state.current_anomaly == "cpu_spike":
        return max(80.0, min(99.0, state.cpu_ema(90) + random.gauss(0, 5)))
    else:
        return max(1.0, min(95.0, state.cpu_ema(p.cpu_base + random.gauss(0, p.cpu_noise))))

def _gen_ram(state: GeneratorState, hw: float) -> float:
    p = state.profile
    if state.mode == "normal":
        return max(10.0, min(90.0, p.ram_base + p.ram_amplitude * _sine(hw, 12) + random.gauss(0, p.ram_noise)))
    elif state.current_anomaly == "memory_leak":
        step = 180 / 4
        state.leak_allocated_mb = min(state.leak_allocated_mb + step, state.total_ram_mb * 0.95)
        leak_pct = state.leak_allocated_mb / state.total_ram_mb * 100
        return max(leak_pct, min(96.0, leak_pct + random.gauss(0, 1)))
    else:
        return max(10.0, min(90.0, p.ram_base + random.gauss(0, p.ram_noise)))

def _gen_disk_io(state: GeneratorState) -> float:
    p = state.profile
    base = p.disk_io_base
    if state.current_anomaly == "disk_pressure":
        base *= 3.0
    io = max(0.0, random.gauss(base, p.disk_io_noise))
    pct_per_sec = p.disk_drift_gb_per_day / 86400 * INTERVAL_SEC
    state.disk_used_gb += io / (1024**3) * INTERVAL_SEC + random.gauss(0, pct_per_sec * 0.5)
    state.disk_used_gb = max(2.0, min(p.disk_total_gb * 0.97, state.disk_used_gb))
    return io

def _gen_net_rx(state: GeneratorState, cpu: float, p: Profile) -> float:
    base = p.net_rx_base
    if state.current_anomaly == "network_anomaly":
        base *= random.choice([0.05, 3.0])
    elif state.current_anomaly == "service_down":
        base *= 0.1
    return max(0.0, random.gauss(base, p.net_rx_noise) + cpu * 2000)

def _gen_net_tx(state: GeneratorState, cpu: float, p: Profile) -> float:
    base = p.net_tx_base
    if state.current_anomaly == "network_anomaly":
        base *= random.choice([0.05, 3.0])
    elif state.current_anomaly == "service_down":
        base *= 0.1
    return max(0.0, random.gauss(base, p.net_tx_noise) + cpu * 1000)

def _gen_processes(state: GeneratorState, cpu: float) -> float:
    p = state.profile
    if state.current_anomaly == "container_crash":
        return max(5, p.proc_base - random.randint(10, 30) + random.randint(-3, 3))
    return state.proc_ema(p.proc_base + cpu * p.proc_cpu_coeff) + random.randint(-p.proc_noise, p.proc_noise)

def _gen_connections(state: GeneratorState, cpu: float) -> float:
    p = state.profile
    if state.current_anomaly == "network_anomaly":
        return random.choice([0, p.conn_base * 3])
    elif state.current_anomaly == "service_down":
        return max(0, p.conn_base - random.randint(10, 40))
    return max(0, p.conn_base + random.randint(-p.conn_noise, p.conn_noise) + cpu * 2)

def _gen_load(state: GeneratorState, cpu: float) -> tuple[float, float, float]:
    p = state.profile
    cpu_norm = cpu / 100
    if state.current_anomaly == "cpu_spike":
        cpu_norm = 0.9
    l1 = cpu_norm * p.load_per_cpu + random.gauss(0, 0.15)
    l5 = cpu_norm * p.load_per_cpu * 0.7 + random.gauss(0, 0.1)
    l15 = cpu_norm * p.load_per_cpu * 0.5 + random.gauss(0, 0.08)
    return max(0, l1), max(0, l5), max(0, l15)

def generate_tick(state: GeneratorState, ts: datetime, session: Session) -> None:
    p = state.profile
    hw = state.hour_of_week(ts)
    state.uptime_sec += INTERVAL_SEC

    if state.mode == "normal":
        elapsed = (ts - _first_ts(session, p.server_id)).total_seconds() / 60
        schedule = p.anomaly_schedule_min
        if state.schedule_idx < len(schedule) and elapsed >= schedule[state.schedule_idx]:
            _start_anomaly(state, ts, session)
    elif state.mode == "anomaly" and state.anomaly_end and ts >= state.anomaly_end:
        _end_anomaly(state, ts, session)

    cpu = _gen_cpu(state, hw)
    ram = _gen_ram(state, hw)
    total_mb = _pick_total_ram(p)
    used_mb = int(total_mb * ram / 100)
    disk_io = _gen_disk_io(state)
    net_rx = _gen_net_rx(state, cpu, p)
    net_tx = _gen_net_tx(state, cpu, p)
    proc = _gen_processes(state, cpu)
    conn = _gen_connections(state, cpu)
    load_1m, load_5m, load_15m = _gen_load(state, cpu)

    cname, cimage = CONTAINER_CONFIG.get(p.name, ("app", "unknown"))
    container_mem_pct = ram * random.uniform(0.3, 0.7)
    if state.current_anomaly == "container_crash":
        container_mem_pct = 0.0
    session.add(ContainerSnapshot(
        server_id=p.server_id,
        container_id=f"ctr-{p.server_id}",
        container_name=cname,
        image=cimage,
        status=state.container_status,
        extra_data={
            "cpu_percentage": round(cpu * random.uniform(0.1, 0.3), 2),
            "memory_usage_mb": int(container_mem_pct / 100 * 512),
            "memory_percentage": round(container_mem_pct, 2),
            "restart_count": 1 if state.current_anomaly == "container_crash" else 0,
            "health_status": "unhealthy" if state.container_status == "stopped" else "healthy",
        },
        collected_at=ts,
    ))

    row = MetricSnapshot(
        server_id=p.server_id,
        collected_at=ts,
        cpu_usage_percent=round(cpu, 2),
        load_average_1m=round(load_1m, 2),
        load_average_5m=round(load_5m, 2),
        load_average_15m=round(load_15m, 2),
        memory_total_mb=total_mb,
        memory_used_mb=used_mb,
        memory_free_mb=int(total_mb - used_mb),
        memory_usage_percent=round(ram, 2),
        disk_total_gb=p.disk_total_gb,
        disk_used_gb=round(state.disk_used_gb, 2),
        disk_free_gb=round(p.disk_total_gb - state.disk_used_gb, 2),
        disk_usage_percent=round(state.disk_used_gb / p.disk_total_gb * 100, 2),
        network_in_bytes=int(net_rx),
        network_out_bytes=int(net_tx),
        disk_read_bytes=int(disk_io * 0.6),
        disk_write_bytes=int(disk_io * 0.4),
        uptime_seconds=int(state.uptime_sec),
        process_count=int(proc),
        active_connections=int(conn),
    )
    session.add(row)

COMMIT_EVERY = 500

def main() -> None:
    profile_name = os.environ.get("PROFILE", "").strip()
    if not profile_name or profile_name not in PROFILES:
        logger.error("PROFILE must be one of: %s", list(PROFILES.keys()))
        sys.exit(1)

    profile = PROFILES[profile_name]
    server_id_env = os.environ.get("SERVER_ID")
    if server_id_env:
        profile.server_id = int(server_id_env)

    speedup = int(os.environ.get("SPEEDUP", "1"))
    if speedup < 1:
        speedup = 1

    db_url = _TRAINBED_DB_URL

    engine = create_engine(db_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    try:
        existing = session.get(Server, profile.server_id)
        if not existing:
            session.add(Server(
                id=profile.server_id,
                name=f"trainbed-{profile_name}",
                host=f"trainbed-{profile_name}",
                port=22,
                connection_type="ssh",
                environment="dev",
                tags=[profile_name, "trainbed"],
                status="online",
                last_seen=datetime.utcnow(),
            ))
            session.commit()
            logger.info("[srv=%d] Created server record", profile.server_id)
    finally:
        session.close()

    state = GeneratorState(profile)
    running = True
    rows_since_commit = 0
    logical_ts = datetime.utcnow()

    def _stop(_sig, _frame):
        nonlocal running
        running = False
        logger.info("[srv=%d] Shutting down...", profile.server_id)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    logger.info(
        "[srv=%d] %s started | speedup=%dx anomalies=%s schedule=%s",
        profile.server_id, profile.label, speedup,
        profile.anomaly_types, profile.anomaly_schedule_min,
    )

    while running:
        try:
            tick_start = time.monotonic()
            session = SessionLocal()
            try:
                generate_tick(state, logical_ts, session)
                rows_since_commit += 1
                if rows_since_commit >= COMMIT_EVERY:
                    session.commit()
                    rows_since_commit = 0
                session.commit()
                rows_since_commit = 0
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

            logical_ts += timedelta(seconds=INTERVAL_SEC)
            elapsed = time.monotonic() - tick_start
            target_sleep = (INTERVAL_SEC / speedup) - elapsed
            if target_sleep > 0:
                time.sleep(target_sleep)
        except Exception as exc:
            logger.error("[srv=%d] Error: %s", profile.server_id, exc, exc_info=True)
            time.sleep(1)

    logger.info("[srv=%d] Stopped. Uptime=%.1fh", profile.server_id, state.uptime_sec / 3600)

if __name__ == "__main__":
    main()
