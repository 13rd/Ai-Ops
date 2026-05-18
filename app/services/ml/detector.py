"""Anomaly detection — rule-based fallback + LSTM Autoencoder.

`RuleBasedDetector` keeps the original threshold logic as the fallback when
no ML models are loaded. `AutoencoderDetector` consumes a 60-row window from
the metric history and returns a candidate if the AE reconstruction error
exceeds the calibrated threshold. The downstream pipeline classifies the
anomaly type via the CNN-LSTM classifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.models.anomaly import AnomalySeverity, AnomalyType
from app.models.metric import MetricSnapshot
from app.models.server import Server, ServerStatus
from ml.config import WINDOW_SIZE
from ml.features import extract_features


@dataclass
class AnomalyCandidate:
    anomaly_type: str
    severity: str
    score: float  # normalised 0..1+ score, role of reconstruction_error
    threshold: float
    features: dict[str, float] = field(default_factory=dict)
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)
    # AutoencoderDetector fills these for downstream classifier/explainer.
    window: Optional[np.ndarray] = None  # shape (1, 60, 10), scaled
    window_recon: Optional[np.ndarray] = None
    source: str = "rule_based"


# Thresholds are intentionally simple. The pipeline's contract is the
# interface, not these numbers — once the LSTM model is plugged in, this
# whole class is replaced.
CPU_HIGH = 90.0
CPU_CRITICAL = 95.0
MEM_HIGH = 90.0
MEM_CRITICAL = 95.0
DISK_HIGH = 90.0
DISK_CRITICAL = 95.0
LOAD_AVG_HIGH_PER_CPU = 2.0


class RuleBasedDetector:
    @staticmethod
    def detect(server: Server, latest: Optional[MetricSnapshot]) -> list[AnomalyCandidate]:
        candidates: list[AnomalyCandidate] = []

        if server.status == ServerStatus.OFFLINE.value:
            candidates.append(
                AnomalyCandidate(
                    anomaly_type=AnomalyType.SERVICE_DOWN.value,
                    severity=AnomalySeverity.CRITICAL.value,
                    score=1.0,
                    threshold=1.0,
                    features={"status_offline": 1.0},
                    metrics_snapshot={"server_status": server.status},
                )
            )

        if latest is None:
            return candidates

        snapshot = _serialize_snapshot(latest)

        # CPU spike
        cpu = latest.cpu_usage_percent
        if cpu is not None and cpu >= CPU_HIGH:
            severity = (
                AnomalySeverity.HIGH.value if cpu >= CPU_CRITICAL else AnomalySeverity.MEDIUM.value
            )
            candidates.append(
                AnomalyCandidate(
                    anomaly_type=AnomalyType.CPU_SPIKE.value,
                    severity=severity,
                    score=cpu / 100.0,
                    threshold=CPU_HIGH / 100.0,
                    features=_top_cpu_features(latest),
                    metrics_snapshot=snapshot,
                )
            )

        # Memory pressure → memory_leak (stub heuristic)
        mem = latest.memory_usage_percent
        if mem is not None and mem >= MEM_HIGH:
            severity = (
                AnomalySeverity.HIGH.value if mem >= MEM_CRITICAL else AnomalySeverity.MEDIUM.value
            )
            candidates.append(
                AnomalyCandidate(
                    anomaly_type=AnomalyType.MEMORY_LEAK.value,
                    severity=severity,
                    score=mem / 100.0,
                    threshold=MEM_HIGH / 100.0,
                    features=_top_memory_features(latest),
                    metrics_snapshot=snapshot,
                )
            )

        # Disk pressure
        disk = latest.disk_usage_percent
        if disk is not None and disk >= DISK_HIGH:
            severity = (
                AnomalySeverity.HIGH.value
                if disk >= DISK_CRITICAL
                else AnomalySeverity.MEDIUM.value
            )
            candidates.append(
                AnomalyCandidate(
                    anomaly_type=AnomalyType.DISK_PRESSURE.value,
                    severity=severity,
                    score=disk / 100.0,
                    threshold=DISK_HIGH / 100.0,
                    features=_top_disk_features(latest),
                    metrics_snapshot=snapshot,
                )
            )

        return candidates


# Backwards-compatible alias — existing pipeline imports `AnomalyDetector`.
AnomalyDetector = RuleBasedDetector


class AutoencoderDetector:
    """LSTM AE detector. Returns at most one candidate per call."""

    def __init__(self, registry):
        self.registry = registry

    def detect(
        self, server_name: str, snapshots: list[MetricSnapshot]
    ) -> Optional[AnomalyCandidate]:
        if len(snapshots) < WINDOW_SIZE:
            return None
        scaler = self.registry.get_scaler(server_name)
        if scaler is None:
            return None
        tail = snapshots[-WINDOW_SIZE:]
        df = _snapshots_to_df(tail)
        raw = extract_features(df)
        X = scaler.transform(raw).astype(np.float32).reshape(1, WINDOW_SIZE, 10)
        X_hat = self.registry.ae.predict(X, verbose=0)
        err = float(np.mean((X - X_hat) ** 2))
        if err <= self.registry.threshold:
            return None
        std = self.registry.threshold_std or 1.0
        z = (err - self.registry.threshold_mean) / std
        severity = (
            AnomalySeverity.LOW.value if z < 1
            else AnomalySeverity.MEDIUM.value if z < 2
            else AnomalySeverity.HIGH.value if z < 3
            else AnomalySeverity.CRITICAL.value
        )
        return AnomalyCandidate(
            anomaly_type="unknown",  # classifier fills in
            severity=severity,
            score=err,
            threshold=float(self.registry.threshold),
            features={"reconstruction_error": err, "z_score": float(z)},
            metrics_snapshot=_serialize_snapshot(tail[-1]),
            window=X,
            window_recon=X_hat,
            source="autoencoder",
        )


def _snapshots_to_df(snaps: list[MetricSnapshot]) -> pd.DataFrame:
    def _extra(s, key, default):
        return (s.extra_data or {}).get(key, default)

    return pd.DataFrame([{
        "timestamp": s.collected_at,
        "cpu_usage_percent": s.cpu_usage_percent or 0.0,
        "load_average_1m": s.load_average_1m or 0.0,
        "memory_usage_percent": s.memory_usage_percent or 0.0,
        "swap_used_mb": _extra(s, "swap_used_mb", 0.0),
        "disk_usage_percent": s.disk_usage_percent or 0.0,
        "disk_read_bytes": s.disk_read_bytes or 0,
        "disk_write_bytes": s.disk_write_bytes or 0,
        "network_in_bytes": s.network_in_bytes or 0,
        "network_out_bytes": s.network_out_bytes or 0,
        "containers": _ratio_to_list(_extra(s, "containers_running_ratio", 1.0)),
    } for s in snaps])


def _ratio_to_list(ratio: float) -> list[dict]:
    running = int(round(max(0.0, min(1.0, ratio)) * 4))
    return (
        [{"status": "running"}] * running
        + [{"status": "stopped"}] * (4 - running)
    )


def _serialize_snapshot(m: MetricSnapshot) -> dict[str, Any]:
    return {
        "cpu_usage_percent": m.cpu_usage_percent,
        "memory_usage_percent": m.memory_usage_percent,
        "disk_usage_percent": m.disk_usage_percent,
        "load_average_1m": m.load_average_1m,
        "load_average_5m": m.load_average_5m,
        "load_average_15m": m.load_average_15m,
        "network_in_bytes": m.network_in_bytes,
        "network_out_bytes": m.network_out_bytes,
        "process_count": m.process_count,
        "active_connections": m.active_connections,
        "collected_at": m.collected_at.isoformat() if m.collected_at else None,
    }


def _top_cpu_features(m: MetricSnapshot) -> dict[str, float]:
    feats: dict[str, float] = {}
    if m.cpu_usage_percent is not None:
        feats["cpu_usage_percent"] = m.cpu_usage_percent
    if m.load_average_1m is not None:
        feats["load_average_1m"] = m.load_average_1m
    if m.process_count is not None:
        feats["process_count"] = float(m.process_count)
    return feats


def _top_memory_features(m: MetricSnapshot) -> dict[str, float]:
    feats: dict[str, float] = {}
    if m.memory_usage_percent is not None:
        feats["memory_usage_percent"] = m.memory_usage_percent
    if m.memory_used_mb is not None:
        feats["memory_used_mb"] = m.memory_used_mb
    if m.memory_free_mb is not None:
        feats["memory_free_mb"] = m.memory_free_mb
    return feats


def _top_disk_features(m: MetricSnapshot) -> dict[str, float]:
    feats: dict[str, float] = {}
    if m.disk_usage_percent is not None:
        feats["disk_usage_percent"] = m.disk_usage_percent
    if m.disk_used_gb is not None:
        feats["disk_used_gb"] = m.disk_used_gb
    if m.disk_free_gb is not None:
        feats["disk_free_gb"] = m.disk_free_gb
    return feats
