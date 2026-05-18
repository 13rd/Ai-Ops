"""Pick anomaly threshold from val-normal reconstruction errors (mean + 3·std)."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
from tensorflow import keras

from ml.config import label_to_index


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/lstm_ae.keras")
    ap.add_argument("--data", default="data/processed/dataset.npz")
    ap.add_argument("--out", default="models/threshold.json")
    ap.add_argument("--background-size", type=int, default=100)
    args = ap.parse_args()

    d = np.load(args.data)
    X_val, y_val = d["X_val"], d["y_val"]
    normal = label_to_index("normal")
    Xn = X_val[y_val == normal]

    model = keras.models.load_model(args.model)
    recon = model.predict(Xn, verbose=0)
    mse = np.mean((Xn - recon) ** 2, axis=(1, 2))
    # 80th percentile of val-normal errors — balances precision and recall;
    # downstream classifier filters residual false positives.
    threshold = float(np.percentile(mse, 80))
    payload = {
        "threshold": threshold,
        "mean": float(mse.mean()),
        "std": float(mse.std()),
        "p90": threshold,
        "p95": float(np.percentile(mse, 95)),
    }
    Path(args.out).write_text(json.dumps(payload, indent=2))
    logging.info(
        "threshold=%.6f mean=%.6f std=%.6f",
        payload["threshold"], payload["mean"], payload["std"],
    )

    # SHAP background set for DeepExplainer (val-normal random sample)
    rng = np.random.default_rng(0)
    k = min(args.background_size, len(Xn))
    bg = Xn[rng.choice(len(Xn), size=k, replace=False)]
    bg_path = Path(args.model).parent / "background.npy"
    np.save(bg_path, bg)
    logging.info("saved background set %s shape=%s", bg_path, bg.shape)


if __name__ == "__main__":
    main()
