from __future__ import annotations

import numpy as np

from ml.config import index_to_label

class AnomalyClassifier:
    def __init__(self, registry):
        self.registry = registry

    def classify(self, X_norm: np.ndarray) -> tuple[str, float, np.ndarray]:

        probs = self.registry.classifier.predict(X_norm, verbose=0)[0]
        idx = int(np.argmax(probs))
        return index_to_label(idx), float(probs[idx]), probs
