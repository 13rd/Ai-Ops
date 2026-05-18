"""Coordinator that ties detector → classifier → explainer → recommender.

Picks the AE+classifier path when models are loaded in the registry, falls
back to the rule-based detector when they're not. Dedupes consecutive
anomalies of the same type per server.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import Anomaly, AnomalyStatus
from app.models.metric import MetricSnapshot
from app.models.recommendation import Recommendation
from app.models.server import Server
from app.services.ml.classifier import AnomalyClassifier
from app.services.ml.detector import (
    AnomalyCandidate,
    AutoencoderDetector,
    RuleBasedDetector,
    _serialize_snapshot,
)
from app.services.ml.explainer import Explainer
from app.services.ml.recommender import Recommender
from app.services.ml.registry import get_registry
from app.services.notifications.dispatcher import NotificationDispatcher
from ml.config import WINDOW_SIZE, label_to_index

logger = logging.getLogger(__name__)


class MLPipeline:
    @staticmethod
    async def analyze(
        db: AsyncSession,
        server: Server,
        *,
        commit: bool = True,
        dispatch_notifications: bool = True,
    ) -> list[Anomaly]:
        registry = get_registry()
        if registry.has_models():
            return await MLPipeline._analyze_ml(
                db, server, registry,
                commit=commit, dispatch_notifications=dispatch_notifications,
            )
        return await MLPipeline._analyze_rule_based(
            db, server, commit=commit, dispatch_notifications=dispatch_notifications,
        )

    # ------------------------------------------------------------------
    # Rule-based fallback (legacy behavior)
    # ------------------------------------------------------------------
    @staticmethod
    async def _analyze_rule_based(
        db: AsyncSession, server: Server, *, commit: bool, dispatch_notifications: bool,
    ) -> list[Anomaly]:
        latest = await MLPipeline._fetch_latest_metric(db, server.id)
        candidates = RuleBasedDetector.detect(server, latest)
        return await MLPipeline._persist_and_dispatch(
            db, server, candidates, commit=commit,
            dispatch_notifications=dispatch_notifications,
        )

    # ------------------------------------------------------------------
    # ML path: AE → classifier → explainer → recommender
    # ------------------------------------------------------------------
    @staticmethod
    async def _analyze_ml(
        db: AsyncSession, server: Server, registry, *,
        commit: bool, dispatch_notifications: bool,
    ) -> list[Anomaly]:
        snaps = await MLPipeline._fetch_recent_snapshots(db, server.id, WINDOW_SIZE)
        if len(snaps) < WINDOW_SIZE:
            return []

        candidate = AutoencoderDetector(registry).detect(server.name, snaps)
        if candidate is None:
            return []

        cls_label, confidence, _probs = AnomalyClassifier(registry).classify(
            candidate.window
        )
        if cls_label == "normal":
            return []
        candidate.anomaly_type = cls_label
        candidate.features["confidence"] = confidence

        explanation = Explainer(registry).explain_window(
            candidate.window, candidate.window_recon, class_idx=label_to_index(cls_label),
        )

        return await MLPipeline._persist_and_dispatch(
            db, server, [candidate], commit=commit,
            dispatch_notifications=dispatch_notifications,
            explanation_override=explanation,
            use_ollama=True,
        )

    # ------------------------------------------------------------------
    # Shared persistence + notification logic
    # ------------------------------------------------------------------
    @staticmethod
    async def _persist_and_dispatch(
        db: AsyncSession,
        server: Server,
        candidates: list[AnomalyCandidate],
        *,
        commit: bool,
        dispatch_notifications: bool,
        explanation_override: Optional[list[dict]] = None,
        use_ollama: bool = False,
    ) -> list[Anomaly]:
        if not candidates:
            return []
        existing_open = await MLPipeline._open_anomaly_types(db, server.id)
        created: list[Anomaly] = []
        recommender = Recommender() if use_ollama else None

        for candidate in candidates:
            if candidate.anomaly_type in existing_open:
                logger.debug(
                    "Skipping duplicate %s for server %s (already open)",
                    candidate.anomaly_type, server.id,
                )
                continue
            shap_payload = (
                explanation_override
                if explanation_override is not None
                else Explainer.explain(candidate)
            )
            anomaly = Anomaly(
                server_id=server.id,
                anomaly_type=candidate.anomaly_type,
                severity=candidate.severity,
                reconstruction_error=candidate.score,
                threshold=candidate.threshold,
                shap_explanation=shap_payload,
                metrics_snapshot=candidate.metrics_snapshot,
                status=AnomalyStatus.OPEN.value,
            )
            db.add(anomaly)
            await db.flush()

            if recommender is not None:
                top_feats = shap_payload[:3] if isinstance(shap_payload, list) else None
                draft = await recommender.recommend_async(
                    candidate.anomaly_type, top_feats
                )
            else:
                draft = Recommender.recommend(candidate.anomaly_type)
            db.add(Recommendation(
                anomaly_id=anomaly.id,
                llm_raw_output=draft.llm_raw_output,
                filtered_command=draft.filtered_command,
                explanation=draft.explanation,
            ))
            await db.flush()
            created.append(anomaly)

        if commit and created:
            await db.commit()
            for anomaly in created:
                await db.refresh(anomaly)

        if dispatch_notifications and created:
            for anomaly in created:
                try:
                    await NotificationDispatcher.dispatch_anomaly(db, anomaly)
                except Exception:
                    logger.exception(
                        "Notification dispatch failed for anomaly %s", anomaly.id
                    )

        return created

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    @staticmethod
    async def _fetch_latest_metric(
        db: AsyncSession, server_id: int,
    ) -> Optional[MetricSnapshot]:
        result = await db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.server_id == server_id)
            .order_by(MetricSnapshot.collected_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _fetch_recent_snapshots(
        db: AsyncSession, server_id: int, n: int,
    ) -> list[MetricSnapshot]:
        result = await db.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.server_id == server_id)
            .order_by(MetricSnapshot.collected_at.desc())
            .limit(n)
        )
        rows = list(result.scalars().all())
        return list(reversed(rows))  # chronological

    @staticmethod
    async def _open_anomaly_types(db: AsyncSession, server_id: int) -> set[str]:
        result = await db.execute(
            select(Anomaly.anomaly_type).where(
                Anomaly.server_id == server_id,
                Anomaly.status == AnomalyStatus.OPEN.value,
            )
        )
        return {row for row in result.scalars().all()}


# Re-export for backwards compatibility (used by tests / external callers)
__all__ = ["MLPipeline"]


# Keep the module-level binding so existing imports of _serialize_snapshot
# from app.services.ml.detector still resolve when explainer/registry are
# absent (legacy callers).
_ = _serialize_snapshot
