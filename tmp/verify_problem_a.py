"""Reproduce defect A: byte-counter semantics mismatch blows up the AE gate.

Builds one *normal* 60-step window two ways:
  (1) synthetic semantics  -> per-tick instantaneous byte values (how training data is written)
  (2) real semantics       -> cumulative /proc-style counters (how the live collector reads)

Same scaler (clean-1.pkl), same AE, same threshold. Compares reconstruction MSE.
"""
from __future__ import annotations

import random
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from tensorflow import keras

from ml.features import extract_features

WINDOW = 60
rng = random.Random(7)


def normal_rows() -> list[dict]:
    """60 consecutive normal samples (level metrics identical in both cases)."""
    rows = []
    for k in range(WINDOW + 1):  # +1 so diff() yields 60 usable rate rows
        cpu = max(8.0, min(60.0, rng.gauss(30.0, 4.5)))
        rows.append(dict(
            cpu_usage_percent=round(cpu, 2),
            load_average_1m=round(cpu / 100 * 8 * 0.85, 2),
            memory_usage_percent=round(rng.gauss(38.0, 2.5), 2),
            swap_used_mb=round(rng.gauss(40, 20), 1),
            disk_usage_percent=round(rng.gauss(40, 2), 2),
            # per-tick instantaneous deltas ~150-220k (synthetic generator values)
            _d_read=max(0, rng.gauss(180_000, 60_000)),
            _d_write=max(0, rng.gauss(140_000, 50_000)),
            _d_in=max(5_000, rng.gauss(220_000, 45_000)),
            _d_out=max(5_000, rng.gauss(120_000, 25_000)),
            containers=[{"status": "running"}] * 4,
        ))
    return rows


def to_df(rows: list[dict], cumulative: bool) -> pd.DataFrame:
    recs = []
    acc = dict(read=10_000_000.0, write=8_000_000.0, in_=500_000_000.0, out_=300_000_000.0)
    for r in rows:
        rec = dict(r)
        if cumulative:
            acc["read"] += r["_d_read"]; acc["write"] += r["_d_write"]
            acc["in_"] += r["_d_in"];    acc["out_"] += r["_d_out"]
            rec["disk_read_bytes"] = int(acc["read"])
            rec["disk_write_bytes"] = int(acc["write"])
            rec["network_in_bytes"] = int(acc["in_"])
            rec["network_out_bytes"] = int(acc["out_"])
        else:  # synthetic: write the per-tick delta directly as the field value
            rec["disk_read_bytes"] = int(r["_d_read"])
            rec["disk_write_bytes"] = int(r["_d_write"])
            rec["network_in_bytes"] = int(r["_d_in"])
            rec["network_out_bytes"] = int(r["_d_out"])
        recs.append(rec)
    return pd.DataFrame(recs)


def main() -> None:
    rows = normal_rows()
    scaler = joblib.load(Path("models/scalers/clean-1.pkl"))
    ae = keras.models.load_model("models/lstm_ae.keras")
    import json
    thr = json.loads(Path("models/threshold.json").read_text())["threshold"]

    for label, cumulative in (("SYNTHETIC (instantaneous)", False),
                              ("REAL (cumulative /proc)", True)):
        df = to_df(rows, cumulative=cumulative)
        feats = extract_features(df)            # (61,10); drop first (diff NaN->0)
        feats = feats[1:]                       # 60 usable rows
        scaled = scaler.transform(feats).astype(np.float32)
        win = scaled[np.newaxis, :, :]          # (1,60,10)
        recon = ae.predict(win, verbose=0)
        mse = float(np.mean((win - recon) ** 2))
        net_in_raw = feats[:, 7].mean()         # net_in_bps column
        net_in_scaled = scaled[:, 7].mean()
        fires = "ANOMALY" if mse > thr else "normal"
        print(f"\n=== {label} ===")
        print(f"  net_in_bps  raw mean    = {net_in_raw:,.1f}")
        print(f"  net_in_bps  scaled mean = {net_in_scaled:,.1f}")
        print(f"  recon MSE              = {mse:,.4f}")
        print(f"  threshold              = {thr:.4f}  -> AE verdict: {fires}")


if __name__ == "__main__":
    main()
