from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.preprocessing import StandardScaler

from ml.config import WINDOW_SIZE
from ml.features import extract_features

logger = logging.getLogger(__name__)

SCALERS_DIR = Path("models/scalers")

def fit_server_scaler(server_name: str, normal_df: pd.DataFrame) -> StandardScaler:

    feats = extract_features(normal_df, as_frame=True)
    scaler = StandardScaler().fit(feats.to_numpy())
    SCALERS_DIR.mkdir(parents=True, exist_ok=True)
    out = SCALERS_DIR / f"{server_name}.pkl"
    joblib.dump(scaler, out)
    logger.info("fitted scaler for %s on %d rows -> %s", server_name, len(feats), out)
    return scaler

def snapshots_to_df(snaps) -> pd.DataFrame:

    def _ratio(extra) -> float:
        return (extra or {}).get("containers_running_ratio", 1.0)

    def _swap(extra) -> float:
        return (extra or {}).get("swap_used_mb", 0.0)

    return pd.DataFrame([{
        "timestamp": s.collected_at,
        "cpu_usage_percent": s.cpu_usage_percent or 0.0,
        "load_average_1m": s.load_average_1m or 0.0,
        "memory_usage_percent": s.memory_usage_percent or 0.0,
        "swap_used_mb": _swap(s.extra_data),
        "disk_usage_percent": s.disk_usage_percent or 0.0,
        "disk_read_bytes": s.disk_read_bytes or 0,
        "disk_write_bytes": s.disk_write_bytes or 0,
        "network_in_bytes": s.network_in_bytes or 0,
        "network_out_bytes": s.network_out_bytes or 0,
        "containers": (
            [{"status": "running"} for _ in range(int(round(_ratio(s.extra_data) * 4)))]
            + [{"status": "stopped"} for _ in range(4 - int(round(_ratio(s.extra_data) * 4)))]
        ),
    } for s in snaps])

async def calibrate_from_db(
    server_name: str, *, min_rows: int = WINDOW_SIZE,
) -> StandardScaler | None:

    from sqlalchemy import select

    from app.db.base import AsyncSessionLocal
    from app.models.metric import MetricSnapshot
    from app.models.server import Server

    async with AsyncSessionLocal() as db:
        srv = (await db.execute(
            select(Server).where(Server.name == server_name)
        )).scalar_one_or_none()
        if srv is None:
            logger.warning("calibrate: server %s not found", server_name)
            return None
        snaps = (await db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.server_id == srv.id)
            .order_by(MetricSnapshot.collected_at)
        )).scalars().all()

    if len(snaps) < min_rows:
        logger.warning(
            "calibrate: %s has only %d normal rows (<%d). Collect more, then run "
            "`python -m ml.calibration %s`.",
            server_name, len(snaps), min_rows, server_name,
        )
        return None

    return fit_server_scaler(server_name, snapshots_to_df(snaps))

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Fit a per-server scaler from DB normals.")
    ap.add_argument("server_name")
    ap.add_argument("--min-rows", type=int, default=WINDOW_SIZE)
    args = ap.parse_args()
    scaler = asyncio.run(calibrate_from_db(args.server_name, min_rows=args.min_rows))
    if scaler is None:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
