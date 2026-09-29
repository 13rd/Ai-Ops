from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.server import Server, ServerStatus
from app.services.ml.pipeline import MLPipeline
from app.services.ml.registry import get_registry
from app.services.ml.scaler_calibration import calibrate_if_needed

logger = logging.getLogger(__name__)

class MLAnalysisJob:
    def __init__(self):
        self.running = False
        self.task: asyncio.Task | None = None

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._loop(), name="ml-analysis-job")
        logger.info(
            "MLAnalysisJob started (interval=%ss)",
            settings.ML_INFERENCE_INTERVAL_SEC,
        )

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _loop(self) -> None:
        while self.running:
            try:
                await self._iterate()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("MLAnalysisJob iteration crashed")
            await asyncio.sleep(settings.ML_INFERENCE_INTERVAL_SEC)

    async def _iterate(self) -> None:
        async with AsyncSessionLocal() as session:
            srvs = (await session.execute(
                select(Server).where(Server.status == ServerStatus.ONLINE.value)
            )).scalars().all()
            registry = get_registry()
            for s in srvs:
                try:
                    await MLPipeline._auto_resolve_stale(session, s.id)
                    await calibrate_if_needed(session, s.name, s.id, registry)
                    created = await MLPipeline.analyze(session, s)
                    if created:
                        logger.info(
                            "MLAnalysisJob: %d anomaly(ies) for server %s",
                            len(created), s.name,
                        )
                except Exception:
                    logger.exception(
                        "ML analysis failed for server %s", s.id,
                    )
