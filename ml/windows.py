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
) -> tuple[np.ndarray, list[str]]:
    if len(X) != len(labels):
        raise ValueError("X and labels must align")
    if len(X) < window_size:
        return np.empty((0, window_size, X.shape[1]), dtype=np.float32), []

    n = (len(X) - window_size) // stride + 1
    wins = np.stack([X[i * stride : i * stride + window_size] for i in range(n)])
    wlabels: list[str] = []
    half = window_size / 2
    for i in range(n):
        chunk = labels[i * stride : i * stride + window_size]
        counts = Counter(c for c in chunk if c and c != "normal")
        if counts:
            top_type, top_count = counts.most_common(1)[0]
            if top_count >= half:
                wlabels.append(top_type)
                continue
        wlabels.append("normal")
    return wins.astype(np.float32), wlabels
