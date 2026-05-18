"""Train CNN-LSTM classifier on all labeled windows with class weighting."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras

from ml.config import CLASSES
from ml.models.cnn_lstm_classifier import build_cnn_lstm_classifier


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/processed/dataset.npz")
    ap.add_argument("--out", default="models/classifier.keras")
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    d = np.load(args.data)
    X_train, y_train = d["X_train"], d["y_train"]
    X_val, y_val = d["X_val"], d["y_val"]

    classes_present = np.unique(y_train)
    w = compute_class_weight(class_weight="balanced", classes=classes_present, y=y_train)
    cw = {int(c): float(wi) for c, wi in zip(classes_present, w)}
    # ensure all classes have a weight even if some are missing in train
    for i in range(len(CLASSES)):
        cw.setdefault(i, 1.0)
    logging.info("class_weights=%s", cw)

    model = build_cnn_lstm_classifier()
    es = keras.callbacks.EarlyStopping(
        monitor="val_accuracy", patience=15, restore_best_weights=True
    )
    model.fit(
        X_train, y_train, validation_data=(X_val, y_val),
        epochs=args.epochs, batch_size=args.batch,
        class_weight=cw, callbacks=[es], verbose=2,
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    model.save(args.out)
    logging.info("saved %s", args.out)


if __name__ == "__main__":
    main()
