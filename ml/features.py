from __future__ import annotations

import numpy as np
import pandas as pd

from ml.config import FEATURE_COLS

SAMPLE_INTERVAL_SEC = 15.0

RATE_COLS = ("disk_read_bps", "disk_write_bps", "net_in_bps", "net_out_bps")

def _containers_running_ratio(containers) -> float:
    if not containers:
        return 1.0
    running = sum(1 for c in containers if (c or {}).get("status") == "running")
    return running / len(containers)

def _rate(series: pd.Series, dt: pd.Series) -> pd.Series:

    diff = series.diff()
    diff = diff.where(diff >= 0, 0.0).fillna(0.0)
    return diff / dt

def _elapsed_seconds(df: pd.DataFrame) -> pd.Series:

    if "timestamp" not in df.columns:
        return pd.Series(SAMPLE_INTERVAL_SEC, index=df.index, dtype=float)
    ts = pd.to_datetime(df["timestamp"])
    dt = ts.diff().dt.total_seconds()
    return dt.fillna(SAMPLE_INTERVAL_SEC).clip(lower=1.0)

def extract_features(df: pd.DataFrame, *, as_frame: bool = False):

    if "containers" in df.columns:
        running_ratio = df["containers"].apply(_containers_running_ratio)
    else:
        running_ratio = pd.Series(np.ones(len(df)), index=df.index)

    dt = _elapsed_seconds(df)

    out = pd.DataFrame(index=df.index)
    out["cpu_percent"] = df["cpu_usage_percent"].astype(float)
    out["load_avg_1m"] = df["load_average_1m"].astype(float)
    out["mem_percent"] = df["memory_usage_percent"].astype(float)
    swap = df["swap_used_mb"] if "swap_used_mb" in df.columns else 0.0
    out["swap_used_mb"] = pd.Series(swap, index=df.index).astype(float) \
        if not isinstance(swap, pd.Series) else swap.astype(float)
    out["disk_percent"] = df["disk_usage_percent"].astype(float)
    out["disk_read_bps"] = _rate(df["disk_read_bytes"].astype(float), dt)
    out["disk_write_bps"] = _rate(df["disk_write_bytes"].astype(float), dt)
    out["net_in_bps"] = _rate(df["network_in_bytes"].astype(float), dt)
    out["net_out_bps"] = _rate(df["network_out_bytes"].astype(float), dt)
    out["containers_running_ratio"] = running_ratio.astype(float)

    for col in RATE_COLS:
        out[col] = np.log1p(out[col])

    out = out[FEATURE_COLS].fillna(0.0)
    return out if as_frame else out.to_numpy(dtype=np.float32)
