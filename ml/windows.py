from __future__ import annotations

import numpy as np

def build_windows(
    X: np.ndarray,
    labels: list[str],
    *,
    window_size: int = 60,
    stride: int = 4,
    min_tail: int = 10,
) -> tuple[np.ndarray, list[str]]:

    if len(X) != len(labels):
        raise ValueError("X and labels must align")
    if len(X) < window_size:
        return np.empty((0, window_size, X.shape[1]), dtype=np.float32), []

    n = (len(X) - window_size) // stride + 1
    wins = np.stack([X[i * stride : i * stride + window_size] for i in range(n)])
    wlabels: list[str] = []
    for i in range(n):
        chunk = labels[i * stride : i * stride + window_size]
        last = chunk[-1]
        if last and last != "normal":
            run = 0
            for c in reversed(chunk):
                if c == last:
                    run += 1
                else:
                    break
            if run >= min_tail:
                wlabels.append(last)
                continue
        wlabels.append("normal")
    return wins.astype(np.float32), wlabels
