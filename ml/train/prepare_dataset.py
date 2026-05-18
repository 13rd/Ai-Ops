"""Read MetricSnapshot+AnomalyEvent from DB, build per-server windowed splits."""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.models.anomaly_event import AnomalyEvent
from app.models.metric import MetricSnapshot
from app.models.server import Server
from ml.config import STRIDE, WINDOW_SIZE, label_to_index
from ml.features import extract_features
from ml.windows import build_windows

logger = logging.getLogger(__name__)


async def _load_server(session, server: Server) -> tuple[pd.DataFrame, list[str]]:
    res = await session.execute(
        select(MetricSnapshot)
        .where(MetricSnapshot.server_id == server.id)
        .order_by(MetricSnapshot.collected_at)
    )
    snaps = res.scalars().all()
    if not snaps:
        return pd.DataFrame(), []
    df = pd.DataFrame([{
        "timestamp": s.collected_at,
        "cpu_usage_percent": s.cpu_usage_percent or 0.0,
        "load_average_1m": s.load_average_1m or 0.0,
        "memory_usage_percent": s.memory_usage_percent or 0.0,
        "swap_used_mb": 0.0,  # not in DB schema; default 0
        "disk_usage_percent": s.disk_usage_percent or 0.0,
        "disk_read_bytes": s.disk_read_bytes or 0,
        "disk_write_bytes": s.disk_write_bytes or 0,
        "network_in_bytes": s.network_in_bytes or 0,
        "network_out_bytes": s.network_out_bytes or 0,
        "containers": [],  # ratio defaults to 1.0
    } for s in snaps])

    events = (await session.execute(
        select(AnomalyEvent).where(AnomalyEvent.server_id == server.id)
    )).scalars().all()
    labels: list[str] = ["normal"] * len(df)
    for ev in events:
        end = ev.end_ts or ev.start_ts
        mask = (df["timestamp"] >= ev.start_ts) & (df["timestamp"] <= end)
        for idx in df.index[mask]:
            labels[idx] = ev.scenario_type
    return df, labels


def _split(X: np.ndarray, y: list[str]) -> dict[str, tuple[np.ndarray, list[str]]]:
    n = len(X)
    a, b = int(n * 0.6), int(n * 0.8)
    return {
        "train": (X[:a], y[:a]),
        "val":   (X[a:b], y[a:b]),
        "test":  (X[b:],  y[b:]),
    }


async def prepare(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    scalers_dir = Path("models/scalers")
    scalers_dir.mkdir(parents=True, exist_ok=True)

    all_train_X, all_train_y = [], []
    all_val_X, all_val_y = [], []
    all_test_X, all_test_y = [], []

    async with AsyncSessionLocal() as session:
        servers = (await session.execute(select(Server))).scalars().all()
        for srv in servers:
            df, labels = await _load_server(session, srv)
            if len(df) < WINDOW_SIZE * 2:
                logger.warning("skip %s: only %d rows", srv.name, len(df))
                continue
            X = extract_features(df)
            splits = _split(X, labels)

            tr_X, tr_y = splits["train"]
            normal_mask = np.array([l == "normal" for l in tr_y])
            if normal_mask.sum() < WINDOW_SIZE:
                logger.warning("skip %s scaler: <%d normal rows", srv.name, WINDOW_SIZE)
                continue
            scaler = StandardScaler().fit(tr_X[normal_mask])
            joblib.dump(scaler, scalers_dir / f"{srv.name}.pkl")
            logger.info("server=%s rows=%d normal-train=%d",
                        srv.name, len(df), int(normal_mask.sum()))

            for bucket, accX, accY in (
                ("train", all_train_X, all_train_y),
                ("val", all_val_X, all_val_y),
                ("test", all_test_X, all_test_y),
            ):
                rawX, y = splits[bucket]
                Xn = scaler.transform(rawX).astype(np.float32)
                wins, wlabels = build_windows(Xn, y, window_size=WINDOW_SIZE, stride=STRIDE)
                accX.append(wins)
                accY.extend(wlabels)

    def stack(xs):
        return np.concatenate(xs, axis=0) if xs else np.empty((0, WINDOW_SIZE, 10), dtype=np.float32)

    def encode(ys):
        return np.array([label_to_index(l) for l in ys], dtype=np.int64)

    np.savez_compressed(
        out_dir / "dataset.npz",
        X_train=stack(all_train_X), y_train=encode(all_train_y),
        X_val=stack(all_val_X),     y_val=encode(all_val_y),
        X_test=stack(all_test_X),   y_test=encode(all_test_y),
    )
    logger.info("DONE train=%d val=%d test=%d",
                len(all_train_y), len(all_val_y), len(all_test_y))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/processed")
    args = ap.parse_args()
    asyncio.run(prepare(Path(args.out)))


if __name__ == "__main__":
    main()
