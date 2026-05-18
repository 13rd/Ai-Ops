"""Build sliding windows + apply majority-vote label rule."""
from __future__ import annotations

from collections import Counter

import numpy as np


def build_windows(
    X: np.ndarray,
    labels: list[str],
    *,
    window_size: int = 60,
    stride: int = 4,
    min_anomaly_ratio: float = 0.5,
) -> tuple[np.ndarray, list[str]]:
    """Build sliding windows and assign majority anomaly label.

    `min_anomaly_ratio` — fraction of the window that must share one non-normal
    type for the window to inherit that label. Spec default is 0.5; lower values
    surface short anomaly bursts that don't span half the window.
    """
    if len(X) != len(labels):
        raise ValueError("X and labels must align")
    if len(X) < window_size:
        return np.empty((0, window_size, X.shape[1]), dtype=np.float32), []

    n = (len(X) - window_size) // stride + 1
    wins = np.stack([X[i * stride : i * stride + window_size] for i in range(n)])
    wlabels: list[str] = []
    threshold = window_size * min_anomaly_ratio
    for i in range(n):
        chunk = labels[i * stride : i * stride + window_size]
        counts = Counter(c for c in chunk if c and c != "normal")
        if counts:
            top_type, top_count = counts.most_common(1)[0]
            if top_count >= threshold:
                wlabels.append(top_type)
                continue
        wlabels.append("normal")
    return wins.astype(np.float32), wlabels
