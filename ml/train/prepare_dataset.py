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

TAIL_LABEL_MIN = 10

async def _load_server(session, server: Server) -> tuple[pd.DataFrame, list[str]]:
    res = await session.execute(
        select(MetricSnapshot)
        .where(MetricSnapshot.server_id == server.id)
        .order_by(MetricSnapshot.collected_at)
    )
    snaps = res.scalars().all()
    if not snaps:
        return pd.DataFrame(), []
    def _ratio(extra):
        return (extra or {}).get("containers_running_ratio", 1.0)

    def _swap(extra):
        return (extra or {}).get("swap_used_mb", 0.0)

    df = pd.DataFrame([{
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
        "containers": [
            {"status": "running"} for _ in range(int(round(_ratio(s.extra_data) * 4)))
        ] + [
            {"status": "stopped"} for _ in range(4 - int(round(_ratio(s.extra_data) * 4)))
        ],
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

async def prepare(out_dir: Path, holdout_servers: set[str] | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    scalers_dir = Path("models/scalers")
    scalers_dir.mkdir(parents=True, exist_ok=True)
    holdout_servers = holdout_servers or set()

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

            if srv.name in holdout_servers:
                normal_mask = np.array([l == "normal" for l in labels])
                if normal_mask.sum() < WINDOW_SIZE:
                    logger.warning("skip holdout %s: <%d normal rows", srv.name, WINDOW_SIZE)
                    continue
                scaler = StandardScaler().fit(X[normal_mask])
                joblib.dump(scaler, scalers_dir / f"{srv.name}.pkl")
                Xn = scaler.transform(X).astype(np.float32)
                wins, wlabels = build_windows(
                    Xn, labels, window_size=WINDOW_SIZE,
                    stride=STRIDE, min_tail=TAIL_LABEL_MIN,
                )
                all_test_X.append(wins)
                all_test_y.extend(wlabels)
                logger.info("HOLDOUT server=%s rows=%d -> %d test windows",
                            srv.name, len(df), len(wlabels))
                continue

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

            bucket_cfg = {
                "train": dict(stride=2, min_tail=TAIL_LABEL_MIN),
                "val":   dict(stride=STRIDE, min_tail=TAIL_LABEL_MIN),
                "test":  dict(stride=STRIDE, min_tail=TAIL_LABEL_MIN),
            }
            for bucket, accX, accY in (
                ("train", all_train_X, all_train_y),
                ("val", all_val_X, all_val_y),
                ("test", all_test_X, all_test_y),
            ):
                rawX, y = splits[bucket]
                Xn = scaler.transform(rawX).astype(np.float32)
                wins, wlabels = build_windows(
                    Xn, y, window_size=WINDOW_SIZE, **bucket_cfg[bucket],
                )
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
    ap.add_argument(
        "--holdout-servers", default="",
        help="comma-separated server names routed wholly into the test split",
    )
    args = ap.parse_args()
    holdout = {s.strip() for s in args.holdout_servers.split(",") if s.strip()}
    asyncio.run(prepare(Path(args.out), holdout_servers=holdout))

if __name__ == "__main__":
    main()
