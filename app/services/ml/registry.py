"""Process-singleton wrapper around ml.registry for FastAPI lifespan."""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings
from ml.registry import ModelRegistry

logger = logging.getLogger(__name__)

_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry(models_dir=Path(settings.ML_MODELS_DIR))
    return _registry


def warmup() -> None:
    try:
        get_registry().load()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ML registry warmup failed: %s — using rule-based fallback", exc)
