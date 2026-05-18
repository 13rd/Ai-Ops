"""Register the stress-target Docker container as a server and prep the scaler."""
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from sqlalchemy import select

from app.core.secrets import get_secrets_manager
from app.db.base import AsyncSessionLocal
from app.models.server import Server, ServerStatus

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("bootstrap_stress_target")

NAME = "stress-target"
HOST = "127.0.0.1"
PORT = 2224
USER = "demo"
PASSWORD = "demopass"
SOURCE_SCALER = "clean-1.pkl"


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


def _copy_scaler() -> None:
    src = Path("models/scalers") / SOURCE_SCALER
    dst = Path("models/scalers") / f"{NAME}.pkl"
    if not src.exists():
        raise SystemExit(f"Source scaler {src} missing — train models first.")
    if dst.exists():
        log.info("✓ %s already present", dst)
        return
    shutil.copy2(src, dst)
    log.info("✓ %s copied from %s", dst, src)


async def main() -> None:
    sid = await _ensure_server()
    _copy_scaler()
    log.info("Bootstrap complete (server_id=%d).", sid)
    log.info("Next:  docker compose up -d stress-target")
    log.info("       tail -f server.log | grep -E 'stress-target|MLAnalysis'")


if __name__ == "__main__":
    asyncio.run(main())
