from __future__ import annotations

import argparse
import asyncio
import logging
import random
import time
from datetime import datetime

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.models.metric import MetricSnapshot
from app.models.server import Server
from data_gen.scripts.generate_clean_dataset import (
    _apply_anomaly,
    _normal_sample,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [live-sim] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("live-sim")

CYCLE = [
    "cpu_spike", "memory_leak", "disk_fill",
    "network_storm", "container_crash", "service_down",
]
INTERVAL_SEC = 15
EVENT_LEN_SEC = 60
GAP_SEC = 90

def _running_ratio(containers: list[dict]) -> float:
    if not containers:
        return 1.0
    return sum(1 for c in containers if c.get("status") == "running") / len(containers)

async def _server_id(name: str) -> int:
    async with AsyncSessionLocal() as db:
        srv = (await db.execute(select(Server).where(Server.name == name))).scalar_one_or_none()
        if srv is None:
            raise SystemExit(
                f"Server '{name}' not found — run scripts.bootstrap_demo first."
            )
        return srv.id

async def _emit(server_id: int, sample: dict, atype: str | None) -> None:
    ratio = _running_ratio(sample["containers"])
    async with AsyncSessionLocal() as db:
        db.add(MetricSnapshot(
            server_id=server_id,
            collected_at=datetime.utcnow(),
            cpu_usage_percent=sample["cpu_usage_percent"],
            load_average_1m=sample["load_average_1m"],
            load_average_5m=sample["load_average_5m"],
            load_average_15m=sample["load_average_15m"],
            memory_usage_percent=sample["memory_usage_percent"],
            memory_used_mb=sample["memory_used_mb"],
            memory_free_mb=sample["memory_free_mb"],
            disk_usage_percent=sample["disk_usage_percent"],
            disk_used_gb=sample["disk_used_gb"],
            disk_free_gb=sample["disk_free_gb"],
            network_in_bytes=sample["network_in_bytes"],
            network_out_bytes=sample["network_out_bytes"],
            disk_read_bytes=sample["disk_read_bytes"],
            disk_write_bytes=sample["disk_write_bytes"],
            process_count=sample["process_count"],
            active_connections=sample["active_connections"],
            extra_data={
                "containers_running_ratio": ratio,
                "swap_used_mb": sample["swap_used_mb"],
            },
        ))
        await db.commit()
    label = atype or "normal"
    log.info(
        "emit %-16s cpu=%5.1f mem=%4.1f disk=%4.1f netIn=%6.0fk ratio=%.2f",
        label, sample["cpu_usage_percent"], sample["memory_usage_percent"],
        sample["disk_usage_percent"], sample["network_in_bytes"] / 1000, ratio,
    )

async def main(server_name: str) -> None:
    sid = await _server_id(server_name)
    log.info("Live simulator started for server=%s (id=%d)", server_name, sid)
    rng = random.Random()
    disk_used = 220.0
    cur_event: tuple[float, str, float] | None = None
    cycle_idx = 0
    next_event_at = time.monotonic() + GAP_SEC

    while True:
        now_mono = time.monotonic()
        if cur_event and now_mono >= cur_event[0]:
            log.info("END   %s", cur_event[1])
            cur_event = None
            next_event_at = now_mono + GAP_SEC
        if cur_event is None and now_mono >= next_event_at:
            atype = CYCLE[cycle_idx % len(CYCLE)]
            cycle_idx += 1
            cur_event = (now_mono + EVENT_LEN_SEC, atype, now_mono)
            log.info("START %s", atype)

        sample = _normal_sample(rng, hour=datetime.utcnow().hour, disk_used_gb=disk_used)
        atype_now = None
        if cur_event:
            progress = (now_mono - cur_event[2]) / EVENT_LEN_SEC
            _apply_anomaly(sample, cur_event[1], rng, progress)
            atype_now = cur_event[1]

        await _emit(sid, sample, atype_now)
        disk_used = min(380, max(50, disk_used + rng.gauss(0.0008, 0.003)))
        await asyncio.sleep(INTERVAL_SEC)

def cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="demo-1")
    args = ap.parse_args()
    try:
        asyncio.run(main(args.server))
    except KeyboardInterrupt:
        log.info("Stopped.")

if __name__ == "__main__":
    cli()
