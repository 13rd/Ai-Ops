"""One-shot demo bootstrap.

Creates the demo-1 server, copies clean-1's scaler, seeds the admin user,
and backfills ~60 normal MetricSnapshot rows so the very first
MLAnalysisJob tick has a full window.
"""
from __future__ import annotations

import asyncio
import logging
import random
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.models.metric import MetricSnapshot
from app.models.server import Server, ServerStatus
from data_gen.scripts.generate_clean_dataset import _normal_sample

# Re-use seeder
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.seed_db import seed_users  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("bootstrap_demo")

DEMO_NAME = "demo-1"
SOURCE_SCALER = "clean-1.pkl"
BACKFILL_ROWS = 60
INTERVAL_SEC = 15


async def _ensure_server(name: str) -> int:
    async with AsyncSessionLocal() as db:
        srv = (await db.execute(select(Server).where(Server.name == name))).scalar_one_or_none()
        if srv is None:
            srv = Server(
                name=name,
                host="127.0.0.1",
                port=22,
                status=ServerStatus.ONLINE.value,
                ssh_username="sim",
            )
            db.add(srv)
            await db.commit()
            await db.refresh(srv)
            log.info("✓ %s server created (id=%d)", name, srv.id)
        else:
            srv.status = ServerStatus.ONLINE.value
            await db.commit()
            log.info("✓ %s server already present (id=%d)", name, srv.id)
        return srv.id


def _copy_scaler() -> None:
    src = Path("models/scalers") / SOURCE_SCALER
    dst = Path("models/scalers") / f"{DEMO_NAME}.pkl"
    if not src.exists():
        raise SystemExit(
            f"Source scaler {src} missing — run ml.train.prepare_dataset first."
        )
    if dst.exists():
        log.info("✓ %s already present", dst)
        return
    shutil.copy2(src, dst)
    log.info("✓ %s copied from %s", dst, src)


async def _backfill_snapshots(server_id: int) -> None:
    async with AsyncSessionLocal() as db:
        recent = (await db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.server_id == server_id)
            .order_by(MetricSnapshot.collected_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if recent is not None and (datetime.utcnow() - recent.collected_at).total_seconds() < 60:
            log.info("✓ backfill skipped — recent snapshot at %s", recent.collected_at)
            return

        rng = random.Random(0)
        now = datetime.utcnow().replace(microsecond=0)
        disk = 220.0
        for i in range(BACKFILL_ROWS, 0, -1):
            ts = now - timedelta(seconds=i * INTERVAL_SEC)
            s = _normal_sample(rng, hour=ts.hour, disk_used_gb=disk)
            db.add(MetricSnapshot(
                server_id=server_id,
                collected_at=ts,
                cpu_usage_percent=s["cpu_usage_percent"],
                load_average_1m=s["load_average_1m"],
                load_average_5m=s["load_average_5m"],
                load_average_15m=s["load_average_15m"],
                memory_usage_percent=s["memory_usage_percent"],
                memory_used_mb=s["memory_used_mb"],
                memory_free_mb=s["memory_free_mb"],
                disk_usage_percent=s["disk_usage_percent"],
                disk_used_gb=s["disk_used_gb"],
                disk_free_gb=s["disk_free_gb"],
                network_in_bytes=s["network_in_bytes"],
                network_out_bytes=s["network_out_bytes"],
                disk_read_bytes=s["disk_read_bytes"],
                disk_write_bytes=s["disk_write_bytes"],
                process_count=s["process_count"],
                active_connections=s["active_connections"],
                extra_data={
                    "containers_running_ratio": 1.0,
                    "swap_used_mb": s["swap_used_mb"],
                },
            ))
        await db.commit()
        log.info("✓ backfilled %d normal snapshots ending %s", BACKFILL_ROWS, now)


async def main() -> None:
    await seed_users()
    log.info("✓ admin user ready (admin / admin123)")
    sid = await _ensure_server(DEMO_NAME)
    _copy_scaler()
    await _backfill_snapshots(sid)
    log.info("Bootstrap complete — start backend and live simulator next.")


if __name__ == "__main__":
    asyncio.run(main())
