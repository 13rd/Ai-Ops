"""Evaluate AE precision/recall + classifier macro-F1 on test split."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from tensorflow import keras

from ml.config import CLASSES, label_to_index


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="models")
    ap.add_argument("--data", default="data/processed/dataset.npz")
    ap.add_argument("--out", default="models/eval_report.json")
    args = ap.parse_args()

    d = np.load(args.data)
    X_test, y_test = d["X_test"], d["y_test"]
    normal = label_to_index("normal")

    ae = keras.models.load_model(f"{args.models}/lstm_ae.keras")
    thr = json.loads(Path(f"{args.models}/threshold.json").read_text())["threshold"]
    recon = ae.predict(X_test, verbose=0)
    mse = np.mean((X_test - recon) ** 2, axis=(1, 2))
    ae_pred_anom = (mse > thr).astype(int)
    y_anom = (y_test != normal).astype(int)
    ae_prec = precision_score(y_anom, ae_pred_anom, zero_division=0)
    ae_rec = recall_score(y_anom, ae_pred_anom, zero_division=0)

    clf = keras.models.load_model(f"{args.models}/classifier.keras")
    probs = clf.predict(X_test, verbose=0)
    y_pred = probs.argmax(axis=1)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    normal_mask = y_test == normal
    normal_acc = float((y_pred[normal_mask] == normal).mean()) if normal_mask.any() else 0.0
    present = sorted(set(int(c) for c in np.unique(y_test)) |
                     set(int(c) for c in np.unique(y_pred)))
    target_names = [CLASSES[i] for i in present]
    report = classification_report(
        y_test, y_pred, labels=present, target_names=target_names, zero_division=0
    )

    payload = {
        "ae_precision": float(ae_prec),
        "ae_recall": float(ae_rec),
        "classifier_macro_f1": float(macro_f1),
        "classifier_normal_accuracy": normal_acc,
        "classification_report": report,
    }
    Path(args.out).write_text(json.dumps(payload, indent=2))
    print(json.dumps({k: v for k, v in payload.items() if k != "classification_report"}, indent=2))
    print(report)


if __name__ == "__main__":
    main()
