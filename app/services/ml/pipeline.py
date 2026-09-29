from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
from app.services.ml.llm_settings_service import get_settings as get_llm_settings
from app.services.ml.recommender import Recommender
from app.services.ml.registry import get_registry
from app.services.notifications.dispatcher import NotificationDispatcher
from ml.config import FEATURE_COLS, WINDOW_SIZE, label_to_index

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

    @staticmethod
    async def _analyze_rule_based(
        db: AsyncSession, server: Server, *, commit: bool, dispatch_notifications: bool,
    ) -> list[Anomaly]:
        latest = await MLPipeline._fetch_latest_metric(db, server.id)
        candidates = RuleBasedDetector.detect(server, latest)
        return await MLPipeline._persist_and_dispatch(
            db, server, candidates, commit=commit,
            dispatch_notifications=dispatch_notifications,
            bypass_dedup=settings.ML_DEMO_DISABLE_DEDUP,
        )

    @staticmethod
    async def _analyze_ml(
        db: AsyncSession, server: Server, registry, *,
        commit: bool, dispatch_notifications: bool,
    ) -> list[Anomaly]:
        latest = await MLPipeline._fetch_latest_metric(db, server.id)
        rule_candidates = RuleBasedDetector.detect(server, latest)

        snaps = await MLPipeline._fetch_recent_snapshots(db, server.id, WINDOW_SIZE)
        if len(snaps) < WINDOW_SIZE:
            if rule_candidates:
                return await MLPipeline._persist_and_dispatch(
                    db, server, rule_candidates, commit=commit,
                    dispatch_notifications=dispatch_notifications,
                    bypass_dedup=settings.ML_DEMO_DISABLE_DEDUP,
                )
            return []

        candidate = AutoencoderDetector(registry).detect(server.name, snaps)
        if candidate is None:
            if rule_candidates:
                return await MLPipeline._persist_and_dispatch(
                    db, server, rule_candidates, commit=commit,
                    dispatch_notifications=dispatch_notifications,
                    bypass_dedup=settings.ML_DEMO_DISABLE_DEDUP,
                )
            await MLPipeline._auto_resolve_open(db, server.id)
            return []

        if candidate.per_feature_triggered:
            pf_thr = registry.get_per_feature_thresholds(server.name)
            cls_label = _label_from_reconstruction(candidate.window, candidate.window_recon, pf_thr)
            confidence = 0.5
        else:
            cls_label, confidence, _probs = AnomalyClassifier(registry).classify(
                candidate.window
            )
            if cls_label == "normal":
                cls_label = _label_from_reconstruction(candidate.window, candidate.window_recon)
                confidence = 0.5
        candidate.anomaly_type = cls_label
        candidate.features["confidence"] = confidence

        if not MLPipeline._metric_corroborates(cls_label, latest):
            logger.info(
                "Suppressed false %s on server %s: raw metric is normal",
                cls_label, server.name,
            )
            if rule_candidates:
                return await MLPipeline._persist_and_dispatch(
                    db, server, rule_candidates, commit=commit,
                    dispatch_notifications=dispatch_notifications,
                    bypass_dedup=settings.ML_DEMO_DISABLE_DEDUP,
                )
            await MLPipeline._auto_resolve_open(db, server.id)
            return []

        explanation = Explainer(registry).explain_window(
            candidate.window,
            candidate.window_recon,
            class_idx=label_to_index(cls_label),
            scaler=registry.get_scaler(server.name),
            per_feature_thresholds=registry.get_per_feature_thresholds(server.name),
        )

        created = await MLPipeline._persist_and_dispatch(
            db, server, [candidate], commit=commit,
            dispatch_notifications=dispatch_notifications,
            explanation_override=explanation,
            use_ollama=True,
        )
        rule_candidates = [
            c for c in rule_candidates if c.anomaly_type != candidate.anomaly_type
        ]
        if rule_candidates:
            created += await MLPipeline._persist_and_dispatch(
                db, server, rule_candidates, commit=commit,
                dispatch_notifications=dispatch_notifications,
                bypass_dedup=settings.ML_DEMO_DISABLE_DEDUP,
            )
        return created

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
        bypass_dedup: bool = False,
    ) -> list[Anomaly]:
        if not candidates:
            return []
        existing_open = (
            set() if bypass_dedup else await MLPipeline._open_anomaly_types(db, server.id)
        )
        created: list[Anomaly] = []
        recommender: Recommender | None = None
        if use_ollama:
            llm_settings = await get_llm_settings(db)
            if llm_settings.enabled:
                recommender = Recommender.from_settings(llm_settings)

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

            draft = None
            if recommender is not None:
                try:
                    prompt_context = await MLPipeline._build_prompt_context(
                        db, server, candidate, shap_payload
                    )
                    draft = await recommender.recommend_async(
                        candidate.anomaly_type, prompt_context
                    )
                except Exception:
                    logger.exception(
                        "LLM recommendation failed for %s on server %s; "
                        "falling back to static recommendation",
                        candidate.anomaly_type, server.id,
                    )
            if draft is None:
                draft = Recommender.recommend(candidate.anomaly_type)

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
            db.add(Recommendation(
                anomaly_id=anomaly.id,
                llm_raw_output=draft.llm_raw_output,
                filtered_command=draft.filtered_command,
                explanation=draft.explanation,
            ))
            if commit:
                await db.commit()
                await db.refresh(anomaly)
            else:
                await db.flush()
            created.append(anomaly)

        if dispatch_notifications and created:
            for anomaly in created:
                try:
                    await NotificationDispatcher.dispatch_anomaly(db, anomaly)
                except Exception:
                    logger.exception(
                        "Notification dispatch failed for anomaly %s", anomaly.id
                    )

        return created

    @staticmethod
    def _metric_corroborates(label: str, snapshot: Optional[MetricSnapshot]) -> bool:

        field = _CORROBORATE_FIELD.get(label)
        if field is None or snapshot is None:
            return True
        val = getattr(snapshot, field, None)
        return val is None or val >= settings.ML_CORROBORATION_MIN_PERCENT

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
        return list(reversed(rows))

    @staticmethod
    async def _auto_resolve_open(db: AsyncSession, server_id: int) -> None:

        from sqlalchemy import update as sa_update
        result = await db.execute(
            select(Anomaly.id).where(
                Anomaly.server_id == server_id,
                Anomaly.status == AnomalyStatus.OPEN.value,
            )
        )
        open_ids = list(result.scalars().all())
        if open_ids:
            await db.execute(
                sa_update(Anomaly)
                .where(Anomaly.id.in_(open_ids))
                .values(status=AnomalyStatus.RESOLVED.value, resolved_at=datetime.utcnow())
            )
            await db.commit()
            logger.info(
                "Auto-resolved %d open anomaly(ies) for server %d", len(open_ids), server_id
            )

    @staticmethod
    async def _auto_resolve_stale(db: AsyncSession, server_id: int) -> None:

        from sqlalchemy import update as sa_update
        max_age = datetime.utcnow() - timedelta(minutes=settings.ML_ANOMALY_MAX_OPEN_MIN)
        result = await db.execute(
            select(Anomaly.id).where(
                Anomaly.server_id == server_id,
                Anomaly.status == AnomalyStatus.OPEN.value,
                Anomaly.detected_at < max_age,
            )
        )
        stale_ids = list(result.scalars().all())
        if stale_ids:
            await db.execute(
                sa_update(Anomaly)
                .where(Anomaly.id.in_(stale_ids))
                .values(status=AnomalyStatus.RESOLVED.value, resolved_at=datetime.utcnow())
            )
            await db.commit()
            logger.info(
                "Auto-resolved %d stale open anomaly(ies) for server %d (age > %dmin)",
                len(stale_ids), server_id, settings.ML_ANOMALY_MAX_OPEN_MIN,
            )

    @staticmethod
    async def _open_anomaly_types(db: AsyncSession, server_id: int) -> set[str]:

        grace_cutoff = datetime.utcnow() - timedelta(
            minutes=settings.ML_ANOMALY_DEDUP_GRACE_MIN
        )
        result = await db.execute(
            select(Anomaly.anomaly_type).where(
                Anomaly.server_id == server_id,
                or_(
                    Anomaly.status == AnomalyStatus.OPEN.value,
                    Anomaly.resolved_at >= grace_cutoff,
                ),
            )
        )
        return {row for row in result.scalars().all()}

    @staticmethod
    async def _recent_anomaly_count(
        db: AsyncSession, server_id: int, anomaly_type: str, *, days: int = 7,
    ) -> int:

        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(func.count(Anomaly.id)).where(
                Anomaly.server_id == server_id,
                Anomaly.anomaly_type == anomaly_type,
                Anomaly.detected_at >= cutoff,
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def _build_prompt_context(
        db: AsyncSession,
        server: Server,
        candidate: AnomalyCandidate,
        shap_payload: object,
    ) -> dict[str, str]:

        history_count = await MLPipeline._recent_anomaly_count(
            db, server.id, candidate.anomaly_type
        )
        history_summary = (
            f"за последние 7 дней на этом сервере зафиксировано {history_count} "
            "похожих случаев — проблема повторяется"
            if history_count
            else "ранее на этом сервере подобные аномалии не фиксировались"
        )
        return {
            "severity": _SEVERITY_RU.get(candidate.severity, candidate.severity),
            "server_name": server.name,
            "environment": server.environment or "не указано",
            "metrics_summary": _format_metrics_summary(candidate.metrics_snapshot),
            "top_features": _format_shap_features(shap_payload),
            "history_summary": history_summary,
        }

_CORROBORATE_FIELD: dict[str, str] = {
    "cpu_spike": "cpu_usage_percent",
    "memory_leak": "memory_usage_percent",
    "disk_fill": "disk_usage_percent",
}

_SEVERITY_RU: dict[str, str] = {
    "low": "низкая",
    "medium": "средняя",
    "high": "высокая",
    "critical": "критическая",
}

_METRIC_LABELS_RU: dict[str, str] = {
    "cpu_usage_percent": "CPU",
    "memory_usage_percent": "память",
    "disk_usage_percent": "диск",
    "load_average_1m": "нагрузка(1м)",
    "network_in_bytes": "вход.трафик",
    "network_out_bytes": "исх.трафик",
    "process_count": "процессов",
    "active_connections": "соединений",
}

def _format_metrics_summary(snapshot: dict) -> str:
    if not isinstance(snapshot, dict) or not snapshot:
        return "нет данных"
    parts = []
    for key, label in _METRIC_LABELS_RU.items():
        value = snapshot.get(key)
        if value is None:
            continue
        if isinstance(value, float):
            value = round(value, 1)
        parts.append(f"{label}={value}")
    return "; ".join(parts) if parts else "нет данных"

def _format_shap_features(shap_payload: object) -> str:
    if not isinstance(shap_payload, list) or not shap_payload:
        return "нет данных"
    parts = []
    for item in shap_payload:
        if not isinstance(item, dict):
            continue
        metric = item.get("metric", "?")
        impact = item.get("impact_percent")
        impact_str = f"{impact:.0f}%" if isinstance(impact, (int, float)) else "?"
        parts.append(f"{metric} (вклад {impact_str})")
    return "; ".join(parts) if parts else "нет данных"

def _label_from_reconstruction(
    window: np.ndarray,
    window_recon: np.ndarray,
    per_feature_thresholds: np.ndarray | None = None,
) -> str:

    recent_rows = 20
    feat_mse = ((window - window_recon)[0, -recent_rows:, :] ** 2).mean(axis=0)
    if per_feature_thresholds is not None:
        score = feat_mse / np.maximum(per_feature_thresholds, 1e-9)
    else:
        score = feat_mse
    top_idx = int(np.argmax(score))
    col = FEATURE_COLS[top_idx] if top_idx < len(FEATURE_COLS) else ""

    if col in ("cpu_percent", "load_avg_1m"):
        return "cpu_spike"
    if col in ("mem_percent", "swap_used_mb"):
        return "memory_leak"
    if col in ("disk_percent", "disk_read_bps", "disk_write_bps"):
        return "disk_fill"
    if col in ("net_in_bps", "net_out_bps"):
        return "network_storm"
    if col == "containers_running_ratio":
        ratio = float(window[0, :, top_idx].mean())
        return "container_crash" if ratio < 0.5 else "service_down"
    return "cpu_spike"

__all__ = ["MLPipeline"]

_ = _serialize_snapshot
