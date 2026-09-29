from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
from tensorflow import keras

from ml.config import label_to_index
from ml.models.lstm_autoencoder import build_lstm_autoencoder

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/processed/dataset.npz")
    ap.add_argument("--out", default="models/lstm_ae.keras")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--batch", type=int, default=64)
    args = ap.parse_args()

    d = np.load(args.data)
    X_train, y_train = d["X_train"], d["y_train"]
    X_val, y_val = d["X_val"], d["y_val"]
    normal = label_to_index("normal")

    Xtr = X_train[y_train == normal]
    Xv = X_val[y_val == normal]
    logging.info("AE train=%d val=%d", len(Xtr), len(Xv))

    model = build_lstm_autoencoder()
    es = keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=10, restore_best_weights=True
    )
    model.fit(
        Xtr, Xtr, validation_data=(Xv, Xv),
        epochs=args.epochs, batch_size=args.batch,
        callbacks=[es], verbose=2,
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    model.save(args.out)
    logging.info("saved %s", args.out)

if __name__ == "__main__":
    main()
