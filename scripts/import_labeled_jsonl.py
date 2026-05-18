"""Idempotent ingest: JSONL → metric_snapshots + anomaly_events.

Usage:
    uv run python -m scripts.import_labeled_jsonl tmp/ready/merged_dataset.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import AsyncSessionLocal
from app.models.anomaly_event import AnomalyEvent
from app.models.metric import MetricSnapshot
from app.models.server import Server, ServerStatus

logger = logging.getLogger(__name__)
CHUNK = 1000


async def _get_or_create_server(session: AsyncSession, name: str) -> Server:
    res = await session.execute(select(Server).where(Server.name == name))
    srv = res.scalar_one_or_none()
    if srv:
        return srv
    srv = Server(
        name=name,
        host="127.0.0.1",
        port=22,
        status=ServerStatus.ONLINE.value,
        ssh_username="sim",
    )
    session.add(srv)
    await session.flush()
    return srv


def _snapshot_kwargs(server_id: int, row: dict) -> dict:
    return dict(
        server_id=server_id,
        collected_at=datetime.fromisoformat(row["timestamp"]),
        cpu_usage_percent=row.get("cpu_usage_percent"),
        load_average_1m=row.get("load_average_1m"),
        load_average_5m=row.get("load_average_5m"),
        load_average_15m=row.get("load_average_15m"),
        memory_used_mb=row.get("memory_used_mb"),
        memory_free_mb=row.get("memory_free_mb"),
        memory_usage_percent=row.get("memory_usage_percent"),
        disk_used_gb=row.get("disk_used_gb"),
        disk_free_gb=row.get("disk_free_gb"),
        disk_usage_percent=row.get("disk_usage_percent"),
        network_in_bytes=row.get("network_in_bytes"),
        network_out_bytes=row.get("network_out_bytes"),
        disk_read_bytes=row.get("disk_read_bytes"),
        disk_write_bytes=row.get("disk_write_bytes"),
        uptime_seconds=row.get("uptime_seconds"),
        process_count=row.get("process_count"),
    )


async def import_file(session: AsyncSession, path: Path) -> tuple[int, int]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        return 0, 0
    by_server: dict[str, list[dict]] = {}
    for r in rows:
        name = r.get("server_name") or path.stem
        by_server.setdefault(name, []).append(r)

    inserted_total = 0
    events_total = 0
    for hostname, group in by_server.items():
        srv = await _get_or_create_server(session, hostname)
        group.sort(key=lambda r: r["timestamp"])

        # Idempotency: skip timestamps already present
        existing = set(
            (await session.execute(
                select(MetricSnapshot.collected_at).where(MetricSnapshot.server_id == srv.id)
            )).scalars().all()
        )

        new_rows = [
            r for r in group if datetime.fromisoformat(r["timestamp"]) not in existing
        ]
        for i in range(0, len(new_rows), CHUNK):
            session.add_all([
                MetricSnapshot(**_snapshot_kwargs(srv.id, r)) for r in new_rows[i : i + CHUNK]
            ])
            await session.flush()
        inserted_total += len(new_rows)

        # Anomaly events: group consecutive same-type rows
        cur_type: str | None = None
        start_ts: datetime | None = None
        last_ts: datetime | None = None
        for r in group:
            ts = datetime.fromisoformat(r["timestamp"])
            active = r.get("anomaly_active") and r.get("anomaly_type")
            atype = r.get("anomaly_type") if active else None
            if atype != cur_type:
                if cur_type is not None and start_ts is not None:
                    events_total += await _maybe_insert_event(
                        session, srv.id, cur_type, start_ts, last_ts
                    )
                cur_type = atype
                start_ts = ts if atype else None
            last_ts = ts
        if cur_type is not None and start_ts is not None:
            events_total += await _maybe_insert_event(
                session, srv.id, cur_type, start_ts, last_ts
            )

    await session.commit()
    return inserted_total, events_total


async def _maybe_insert_event(
    session: AsyncSession, server_id: int, atype: str, start_ts: datetime, end_ts: datetime
) -> int:
    exists = await session.execute(
        select(AnomalyEvent).where(
            AnomalyEvent.server_id == server_id,
            AnomalyEvent.scenario_type == atype,
            AnomalyEvent.start_ts == start_ts,
        )
    )
    if exists.scalar_one_or_none():
        return 0
    session.add(AnomalyEvent(
        server_id=server_id,
        scenario_type=atype,
        start_ts=start_ts,
        end_ts=end_ts,
        parameters={"source": "simulator"},
    ))
    return 1


async def _main(paths: list[str]) -> None:
    logging.basicConfig(level=logging.INFO)
    async with AsyncSessionLocal() as session:
        for raw in paths:
            matched = list(Path().glob(raw)) or [Path(raw)]
            for p in matched:
                ins, ev = await import_file(session, Path(p))
                logger.info("Imported %s: %d snapshots, %d events", p, ins, ev)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()
    asyncio.run(_main(args.paths))


if __name__ == "__main__":
    main()
