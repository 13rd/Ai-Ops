from __future__ import annotations

import logging

import numpy as np

from app.services.ml.detector import AnomalyCandidate
from ml.config import FEATURE_COLS

logger = logging.getLogger(__name__)

class Explainer:
    def __init__(self, registry=None):
        self.registry = registry

    @staticmethod
    def explain(candidate: AnomalyCandidate) -> dict | list[dict]:

        if candidate.source == "autoencoder" and candidate.window is not None:
            return Explainer().explain_window(
                candidate.window, candidate.window_recon, class_idx=None
            )
        feats = candidate.features
        if not feats:
            return {}
        total = sum(abs(v) for v in feats.values()) or 1.0
        weights = {name: round(abs(value) / total, 4) for name, value in feats.items()}
        top = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:3]
        return dict(top)

    def explain_window(
        self,
        X: np.ndarray,
        X_hat: np.ndarray,
        class_idx: int | None,
        scaler=None,
        per_feature_thresholds: np.ndarray | None = None,
    ) -> list[dict]:
        recent = 20
        err = (X - X_hat)[:, -recent:, :] ** 2

        if per_feature_thresholds is not None:
            err = err / np.maximum(per_feature_thresholds, 1e-9)
        elif scaler is not None:
            scale_sq = np.maximum(scaler.scale_ ** 2, 1e-8)
            err = err / scale_sq
        ae_imp = np.mean(err, axis=(0, 1))
        ae_share = ae_imp / max(ae_imp.sum(), 1e-12)

        clf_share = None
        if self.registry is not None and class_idx is not None:
            de = self.registry.deep_explainer()
            if de is not None:
                try:
                    shap_vals = de.shap_values(X)
                    shap_class = (
                        shap_vals[class_idx]
                        if isinstance(shap_vals, list)
                        else shap_vals
                    )
                    clf_imp = np.mean(np.abs(shap_class), axis=(0, 1))
                    clf_share = clf_imp / max(clf_imp.sum(), 1e-12)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("SHAP failed at inference: %s", exc)

        combined = ae_share if clf_share is None else 0.2 * ae_share + 0.8 * clf_share

        return [
            {
                "metric": FEATURE_COLS[i],
                "impact_percent": float(combined[i] * 100.0),
                "ae_contribution": float(ae_share[i]),
                "shap_contribution": (
                    float(clf_share[i]) if clf_share is not None else None
                ),
            }
            for i in np.argsort(-combined)
        ]
