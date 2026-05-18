"""Pure ModelRegistry — no FastAPI dependency.

Safe to import from training scripts and tests.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler
from tensorflow import keras

logger = logging.getLogger(__name__)


class ModelRegistry:
    def __init__(self, models_dir: Path | str, scalers_dir: Path | str | None = None):
        self.models_dir = Path(models_dir)
        self.scalers_dir = Path(scalers_dir) if scalers_dir else self.models_dir / "scalers"
        self.ae: keras.Model | None = None
        self.classifier: keras.Model | None = None
        self.threshold: float = 0.0
        self.threshold_mean: float = 0.0
        self.threshold_std: float = 1.0
        self.background: np.ndarray | None = None
        self._scaler_cache: dict[str, StandardScaler] = {}
        self._deep_explainer = None
        self._loaded = False

    def has_models(self) -> bool:
        return self._loaded and self.ae is not None and self.classifier is not None

    def load(self) -> None:
        ae_p = self.models_dir / "lstm_ae.keras"
        clf_p = self.models_dir / "classifier.keras"
        thr_p = self.models_dir / "threshold.json"
        if not (ae_p.exists() and clf_p.exists() and thr_p.exists()):
            logger.warning("ML artifacts missing in %s", self.models_dir)
            return
        self.ae = keras.models.load_model(ae_p)
        self.classifier = keras.models.load_model(clf_p)
        t = json.loads(thr_p.read_text())
        self.threshold = float(t["threshold"])
        self.threshold_mean = float(t.get("mean", 0.0))
        self.threshold_std = float(t.get("std", 1.0)) or 1.0
        bg = self.models_dir / "background.npy"
        if bg.exists():
            self.background = np.load(bg)
        self._loaded = True
        logger.info(
            "ModelRegistry loaded from %s (threshold=%.6f)",
            self.models_dir, self.threshold,
        )

    def get_scaler(self, server_name: str) -> StandardScaler | None:
        if server_name in self._scaler_cache:
            return self._scaler_cache[server_name]
        p = self.scalers_dir / f"{server_name}.pkl"
        if not p.exists():
            return None
        sc = joblib.load(p)
        self._scaler_cache[server_name] = sc
        return sc

    def deep_explainer(self):
        """Lazy-init SHAP DeepExplainer; returns None on failure."""
        if self._deep_explainer is not None:
            return self._deep_explainer
        if self.classifier is None or self.background is None:
            return None
        import shap
        try:
            self._deep_explainer = shap.DeepExplainer(self.classifier, self.background)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DeepExplainer init failed: %s; falling back to MSE-only", exc)
            self._deep_explainer = None
        return self._deep_explainer
