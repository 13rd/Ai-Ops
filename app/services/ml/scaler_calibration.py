from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.metric import MetricSnapshot
from app.services.ml.detector import CPU_HIGH, DISK_HIGH, MEM_HIGH, _snapshots_to_df
from ml.config import WINDOW_SIZE
from ml.features import extract_features

logger = logging.getLogger(__name__)

MIN_CALIBRATION_SAMPLES: int = 60

_FETCH_LIMIT: int = MIN_CALIBRATION_SAMPLES * 3

def _is_clean(snap: MetricSnapshot) -> bool:

    if snap.cpu_usage_percent is not None and snap.cpu_usage_percent >= CPU_HIGH:
        return False
    if snap.memory_usage_percent is not None and snap.memory_usage_percent >= MEM_HIGH:
        return False
    if snap.disk_usage_percent is not None and snap.disk_usage_percent >= DISK_HIGH:
        return False
    return True

_MIN_FEATURE_SCALE: dict[str, float] = {
    "cpu_percent": 5.0,
    "load_avg_1m": 0.1,
    "mem_percent": 2.0,
    "swap_used_mb": 10.0,
    "disk_percent": 2.0,
    "disk_read_bps": 1e4,
    "disk_write_bps": 1e4,
    "net_in_bps": 1e4,
    "net_out_bps": 1e4,
    "containers_running_ratio": 0.05,
}

def _apply_min_variance_floor(scaler: StandardScaler) -> None:

    from ml.config import FEATURE_COLS

    for i, col in enumerate(FEATURE_COLS):
        if col in _MIN_FEATURE_SCALE:
            scaler.scale_[i] = max(float(scaler.scale_[i]), _MIN_FEATURE_SCALE[col])

async def calibrate_if_needed(
    db: AsyncSession,
    server_name: str,
    server_id: int,
    registry,
) -> bool:

    if registry.get_scaler(server_name) is not None:
        return False

    result = await db.execute(
        select(MetricSnapshot)
        .where(MetricSnapshot.server_id == server_id)
        .order_by(MetricSnapshot.collected_at.asc())
        .limit(_FETCH_LIMIT)
    )
    all_snaps = list(result.scalars().all())
    clean_snaps = [s for s in all_snaps if _is_clean(s)]

    if len(clean_snaps) < MIN_CALIBRATION_SAMPLES:
        dirty = len(all_snaps) - len(clean_snaps)
        logger.debug(
            "Scaler calibration for %r deferred: %d/%d clean snapshots "
            "(%d dirty filtered out)",
            server_name, len(clean_snaps), MIN_CALIBRATION_SAMPLES, dirty,
        )
        return False

    snaps = clean_snaps[:MIN_CALIBRATION_SAMPLES]
    df = _snapshots_to_df(snaps)
    features = extract_features(df)

    if np.isnan(features).any() or np.isinf(features).any():
        logger.warning(
            "Scaler calibration for %r skipped: feature matrix contains NaN/Inf",
            server_name,
        )
        return False

    scaler = StandardScaler().fit(features)

    _apply_min_variance_floor(scaler)

    scalers_dir = Path(settings.ML_MODELS_DIR) / "scalers"
    scalers_dir.mkdir(parents=True, exist_ok=True)
    out_path = scalers_dir / f"{server_name}.pkl"
    joblib.dump(scaler, out_path)

    registry._scaler_cache[server_name] = scaler

    _calibrate_threshold(scaler, clean_snaps, server_name, scalers_dir, registry)

    dirty_count = len(all_snaps) - len(clean_snaps)
    logger.info(
        "Scaler auto-calibrated for server %r "
        "(%d clean snapshots, %d dirty discarded) → %s",
        server_name, len(snaps), dirty_count, out_path,
    )

    await _notify_calibration_done(db, server_id, server_name, len(snaps), dirty_count)
    return True

def _calibrate_threshold(
    scaler: StandardScaler,
    clean_snaps: list,
    server_name: str,
    scalers_dir: Path,
    registry,
) -> None:

    if registry.ae is None or len(clean_snaps) < WINDOW_SIZE:
        return

    errors: list[float] = []
    feat_errors: list[list[float]] = []
    for i in range(len(clean_snaps) - WINDOW_SIZE + 1):
        window = clean_snaps[i : i + WINDOW_SIZE]
        df = _snapshots_to_df(window)
        feat = extract_features(df)
        x_norm = scaler.transform(feat).astype(np.float32).reshape(1, WINDOW_SIZE, 10)
        x_hat = registry.ae.predict(x_norm, verbose=0)
        sq_err = (x_norm - x_hat) ** 2
        errors.append(float(np.mean(sq_err)))
        feat_errors.append(sq_err[0].mean(axis=0).tolist())

    if not errors:
        return

    err_arr = np.array(errors)
    mean = float(err_arr.mean())
    std = max(float(err_arr.std()), 0.01)
    thr = max(mean + 3.0 * std, float(registry.threshold))

    per_feat_arr = np.array(feat_errors)
    pf_mean = per_feat_arr.mean(axis=0).tolist()
    pf_std = np.maximum(per_feat_arr.std(axis=0), 1e-6).tolist()
    pf_thr = (per_feat_arr.mean(axis=0) + 3.0 * np.maximum(per_feat_arr.std(axis=0), 1e-6)).tolist()

    thr_data = {
        "threshold": thr,
        "mean": mean,
        "std": std,
        "per_feature": {"mean": pf_mean, "std": pf_std, "threshold": pf_thr},
    }
    thr_path = scalers_dir / f"{server_name}_threshold.json"
    thr_path.write_text(json.dumps(thr_data, indent=2))

    registry._threshold_cache[server_name] = thr_data

    logger.info(
        "Per-server threshold for %r: thr=%.4f (mean=%.4f, std=%.4f) from %d windows",
        server_name, thr, mean, std, len(errors),
    )

async def _notify_calibration_done(
    db: AsyncSession,
    server_id: int,
    server_name: str,
    clean_count: int,
    dirty_count: int,
) -> None:
    from app.services.notifications.dispatcher import NotificationDispatcher

    body_parts = [
        f"ML detection is now active for server «{server_name}».",
        f"Baseline scaler fitted on {clean_count} clean snapshots.",
    ]
    if dirty_count:
        body_parts.append(
            f"{dirty_count} snapshots with anomalous values were excluded from the baseline."
        )
    body_parts.append("The autoencoder will now detect anomalies and send alerts.")

    await NotificationDispatcher.dispatch_server_event(
        db,
        server_id=server_id,
        title=f"ML detection ready: {server_name}",
        body=" ".join(body_parts),
        severity="low",
    )
