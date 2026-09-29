from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select

from app.core.secrets import get_secrets_manager
from app.db.base import AsyncSessionLocal
from app.models.server import Server

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

async def encrypt_all() -> int:
    secrets = get_secrets_manager()
    touched = 0

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Server))
        servers = list(result.scalars().all())

        for server in servers:
            changed = False
            for field in ("ssh_password", "ssh_private_key"):
                value = getattr(server, field)
                if not value:
                    continue
                if secrets.is_encrypted(value):
                    continue
                setattr(server, field, secrets.encrypt(value))
                changed = True
            if changed:
                touched += 1
                logger.info(
                    "Encrypted credentials for server id=%s host=%s", server.id, server.host
                )

        if touched:
            await session.commit()

    return touched

def main() -> int:
    touched = asyncio.run(encrypt_all())
    logger.info("Done. Updated %d server row(s).", touched)
    return 0

if __name__ == "__main__":
    sys.exit(main())
