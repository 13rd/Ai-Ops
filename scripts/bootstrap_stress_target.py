from __future__ import annotations

import asyncio
import logging
import os

from sqlalchemy import select

from app.core.secrets import get_secrets_manager
from app.db.base import AsyncSessionLocal
from app.models.server import Server, ServerStatus
from ml.calibration import calibrate_from_db

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("bootstrap_stress_target")

NAME = "stress-target"
# In full docker-compose the backend reaches the target by service DNS name
# (stress-target:22). From a host-run backend use 127.0.0.1:2224 instead:
#   STRESS_TARGET_HOST=127.0.0.1 STRESS_TARGET_PORT=2224 python scripts/bootstrap_stress_target.py
HOST = os.getenv("STRESS_TARGET_HOST", "stress-target")
PORT = int(os.getenv("STRESS_TARGET_PORT", "22"))
USER = "demo"
PASSWORD = "demopass"

async def _ensure_server() -> int:
    secrets = get_secrets_manager()
    async with AsyncSessionLocal() as db:
        srv = (await db.execute(select(Server).where(Server.name == NAME))).scalar_one_or_none()
        if srv is None:
            srv = Server(
                name=NAME,
                host=HOST,
                port=PORT,
                status=ServerStatus.ONLINE.value,
                ssh_username=USER,
                ssh_password=secrets.encrypt(PASSWORD),
            )
            db.add(srv)
            await db.commit()
            await db.refresh(srv)
            log.info("✓ %s server created (id=%d)", NAME, srv.id)
        else:
            srv.host = HOST
            srv.port = PORT
            srv.ssh_username = USER
            srv.ssh_password = secrets.encrypt(PASSWORD)
            srv.status = ServerStatus.ONLINE.value
            await db.commit()
            log.info("✓ %s server updated (id=%d)", NAME, srv.id)
        return srv.id

async def main() -> None:
    sid = await _ensure_server()
    scaler = await calibrate_from_db(NAME)
    if scaler is None:
        log.info("⚠ scaler not yet fitted — collect normal metrics, then run:")
        log.info("    python -m ml.calibration %s", NAME)
    log.info("Bootstrap complete (server_id=%d).", sid)
    log.info("Next:  docker compose up -d stress-target")
    log.info("       tail -f server.log | grep -E 'stress-target|MLAnalysis'")

if __name__ == "__main__":
    asyncio.run(main())
