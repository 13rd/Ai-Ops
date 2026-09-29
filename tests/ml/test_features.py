import math

import pandas as pd

from ml.config import FEATURE_COLS
from ml.features import extract_features


def _row(**kw):
    base = {
        "timestamp": "2026-05-17T21:59:35",
        "cpu_usage_percent": 12.5,
        "load_average_1m": 0.4,
        "memory_usage_percent": 30.0,
        "swap_used_mb": 0.0,
        "disk_usage_percent": 50.0,
        "disk_read_bytes": 0,
        "disk_write_bytes": 0,
        "network_in_bytes": 0,
        "network_out_bytes": 0,
        "containers": [{"status": "running"}, {"status": "running"}],
    }
    base.update(kw)
    return base


def test_extract_shape_and_columns():
    df = pd.DataFrame([_row(), _row()])
    X = extract_features(df)
    assert X.shape == (2, 10)
    Xf = extract_features(df, as_frame=True)
    assert list(Xf.columns) == FEATURE_COLS


def test_byte_counters_become_bps_with_15s_interval():
    # 150_000 B over 15s -> 10_000 B/s, then log1p-compressed
    df = pd.DataFrame([
        _row(timestamp="2026-05-17T21:59:35", network_in_bytes=0),
        _row(timestamp="2026-05-17T21:59:50", network_in_bytes=150_000),
    ])
    Xf = extract_features(df, as_frame=True)
    assert Xf["net_in_bps"].iloc[0] == 0.0  # log1p(0) == 0
    assert abs(Xf["net_in_bps"].iloc[1] - math.log1p(10_000.0)) < 1e-6


def test_rate_uses_actual_interval_not_constant():
    # 150_000 bytes over a 30s gap -> 5_000 bps (not 10_000 from a fixed 15s)
    df = pd.DataFrame([
        _row(timestamp="2026-05-17T21:59:20", network_in_bytes=0),
        _row(timestamp="2026-05-17T21:59:50", network_in_bytes=150_000),
    ])
    Xf = extract_features(df, as_frame=True)
    assert abs(Xf["net_in_bps"].iloc[1] - math.log1p(5_000.0)) < 1e-6


def test_counter_reset_yields_zero_not_spike():
    # cumulative counter drops (restart/wrap) -> rate 0, never a negative spike
    df = pd.DataFrame([
        _row(timestamp="2026-05-17T21:59:35", disk_write_bytes=900_000),
        _row(timestamp="2026-05-17T21:59:50", disk_write_bytes=1_000),
    ])
    Xf = extract_features(df, as_frame=True)
    assert Xf["disk_write_bps"].iloc[1] == 0.0


def test_containers_running_ratio():
    row = _row(containers=[
        {"status": "running"}, {"status": "running"}, {"status": "stopped"},
    ])
    Xf = extract_features(pd.DataFrame([row]), as_frame=True)
    assert abs(Xf["containers_running_ratio"].iloc[0] - 2 / 3) < 1e-9


def test_empty_containers_yields_one():
    row = _row(containers=[])
    Xf = extract_features(pd.DataFrame([row]), as_frame=True)
    assert Xf["containers_running_ratio"].iloc[0] == 1.0
