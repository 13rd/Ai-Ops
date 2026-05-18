import json

import pytest
from sqlalchemy import select

from app.models.anomaly_event import AnomalyEvent
from app.models.metric import MetricSnapshot
from app.models.server import Server
from scripts.import_labeled_jsonl import import_file


def _row(ts, server, active=False, atype=None, **extra):
    base = {
        "timestamp": ts,
        "server_name": server,
        "anomaly_active": active,
        "anomaly_type": atype,
        "cpu_usage_percent": 10.0,
        "load_average_1m": 0.1,
        "memory_usage_percent": 20.0,
        "swap_used_mb": 0.0,
        "disk_usage_percent": 30.0,
        "disk_read_bytes": 0,
        "disk_write_bytes": 0,
        "network_in_bytes": 0,
        "network_out_bytes": 0,
        "containers": [],
    }
    base.update(extra)
    return base


@pytest.mark.asyncio
async def test_import_creates_server_and_snapshots(tmp_path, db_session):
    p = tmp_path / "anomaly-test.jsonl"
    rows = [
        _row("2026-05-17T21:59:35", "anomaly-test"),
        _row("2026-05-17T21:59:50", "anomaly-test", active=True, atype="cpu_spike"),
        _row("2026-05-17T22:00:05", "anomaly-test", active=True, atype="cpu_spike"),
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows))

    inserted, events = await import_file(db_session, p)
    assert inserted == 3
    assert events == 1

    srv = (await db_session.execute(select(Server).where(Server.name == "anomaly-test"))).scalar_one()
    snaps = (await db_session.execute(
        select(MetricSnapshot).where(MetricSnapshot.server_id == srv.id)
    )).scalars().all()
    assert len(snaps) == 3
    evts = (await db_session.execute(
        select(AnomalyEvent).where(AnomalyEvent.server_id == srv.id)
    )).scalars().all()
    assert len(evts) == 1
    assert evts[0].scenario_type == "cpu_spike"


@pytest.mark.asyncio
async def test_import_is_idempotent(tmp_path, db_session):
    p = tmp_path / "anomaly-test2.jsonl"
    p.write_text(json.dumps(_row("2026-05-17T21:59:35", "anomaly-test2")))
    await import_file(db_session, p)
    inserted, _ = await import_file(db_session, p)
    assert inserted == 0
