from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import confusion_matrix
from tensorflow import keras

from ml.config import CLASSES

DATA = "data/processed/dataset.npz"
MODEL = "models/classifier.keras"
OUT = "docs/confusion_matrix.png"

def main() -> None:
    d = np.load(DATA)
    X_test, y_test = d["X_test"], d["y_test"]
    clf = keras.models.load_model(MODEL)
    y_pred = clf.predict(X_test, verbose=0).argmax(axis=1)

    cm = confusion_matrix(y_test, y_pred, labels=list(range(len(CLASSES))))

    fig, ax = plt.subplots(figsize=(8, 6.8), dpi=200)
    im = ax.imshow(cm, cmap="Blues")

    ax.set_xticks(range(len(CLASSES)))
    ax.set_yticks(range(len(CLASSES)))
    ax.set_xticklabels(CLASSES, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(CLASSES, fontsize=9)
    ax.set_xlabel("Предсказанный класс", fontsize=11)
    ax.set_ylabel("Истинный класс", fontsize=11)

    thresh = cm.max() / 2.0
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            val = cm[i, j]
            if val == 0:
                continue
            ax.text(
                j, i, str(val), ha="center", va="center", fontsize=9,
                color="white" if val > thresh else "black",
            )

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8)
    fig.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    print(f"saved {OUT}")
    print("rows=true, cols=pred")
    print("classes:", CLASSES)
    print(cm)

if __name__ == "__main__":
    main()
