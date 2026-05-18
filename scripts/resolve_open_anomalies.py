"""Resolve all (or per-server) open anomalies so dedup unblocks."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from sqlalchemy import func, select, update

from app.db.base import AsyncSessionLocal
from app.models.anomaly import Anomaly, AnomalyStatus
from app.models.server import Server


async def main(server_name: str | None) -> None:
    async with AsyncSessionLocal() as db:
        where = [Anomaly.status == AnomalyStatus.OPEN.value]
        if server_name:
            srv = (await db.execute(
                select(Server).where(Server.name == server_name)
            )).scalar_one_or_none()
            if srv is None:
                raise SystemExit(f"No server named {server_name!r}")
            where.append(Anomaly.server_id == srv.id)

        cnt = (await db.execute(
            select(func.count()).select_from(Anomaly).where(*where)
        )).scalar()
        print(f"Resolving {cnt} open anomaly row(s){f' for {server_name}' if server_name else ''}…")
        if cnt == 0:
            return
        await db.execute(
            update(Anomaly).where(*where).values(
                status=AnomalyStatus.RESOLVED.value,
                resolved_at=datetime.utcnow(),
            )
        )
        await db.commit()
        print("✓ done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", help="resolve only this server's open anomalies")
    args = ap.parse_args()
    asyncio.run(main(args.server))
