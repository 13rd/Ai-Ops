from __future__ import annotations

import asyncio
import logging

import paramiko
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SSHConnectionError
from app.db.base import get_db
from app.models.anomaly import Anomaly, AnomalyStatus
from app.models.metric import MetricSnapshot
from app.models.server import Server
from app.services.ml.pipeline import MLPipeline
from app.services.servers.connection_service import SSHConnectionService

logger = logging.getLogger(__name__)

router = APIRouter()

_INJECT_CMDS: dict[str, str] = {
    "cpu_spike": (
        "nohup sudo stress-ng --cpu 0 --timeout 300s >/dev/null 2>&1 </dev/null &"
    ),
    "memory_leak": (
        "nohup sudo stress-ng --vm 1 --vm-bytes 80% --timeout 300s >/dev/null 2>&1 </dev/null &"
    ),
    "disk_fill": (
        "nohup sudo dd if=/dev/zero of=/tmp/demo_fill bs=1M count=1024 >/dev/null 2>&1 </dev/null &"
    ),
    "network_storm": (
        # Real eth0 traffic to the iperf3 peer (loopback is ignored by the
        # metrics collector, which counts only eth*/ens*/enp* interfaces).
        "nohup sudo iperf3 -c net-peer -t 300 --bidir -P 4 >/dev/null 2>&1 </dev/null &"
    ),
    "service_down":    "sudo systemctl stop nginx",
    "container_crash": "sudo docker kill $(sudo docker ps -q | head -1) 2>/dev/null || true",
}

_STOP_CMD = (
    "sudo pkill -f stress-ng 2>/dev/null; "
    "sudo pkill -f iperf3 2>/dev/null; "
    "sudo systemctl start nginx 2>/dev/null; "
    "sudo rm -f /tmp/demo_fill* 2>/dev/null; "
    "echo done"
)

async def _get_server(db: AsyncSession, server_id: int) -> Server:
    row = (await db.execute(select(Server).where(Server.id == server_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Server {server_id} not found")
    return row

def _ssh_exec_sync(server: Server, command: str) -> str:

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        kwargs = SSHConnectionService._build_connect_kwargs(server)
        client.connect(**kwargs)
        _, stdout, stderr = client.exec_command(command, timeout=15)
        stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        return out or err or "ok"
    finally:
        try:
            client.close()
        except Exception:
            pass

@router.post("/trigger/{anomaly_type}", summary="SSH-trigger a workload anomaly")
async def trigger_anomaly(
    anomaly_type: str,
    server_id: int = Query(..., description="Target server ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if anomaly_type not in _INJECT_CMDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown anomaly type '{anomaly_type}'. Valid: {sorted(_INJECT_CMDS)}",
        )
    server = await _get_server(db, server_id)
    if server.ssh_username == "sim":
        raise HTTPException(
            status_code=400,
            detail="Server is synthetic (ssh_username=sim). Use /run-ml to trigger detection.",
        )

    loop = asyncio.get_event_loop()
    try:
        cmd = _INJECT_CMDS[anomaly_type]
        result = await loop.run_in_executor(None, _ssh_exec_sync, server, cmd)
    except SSHConnectionError as exc:
        raise HTTPException(status_code=503, detail=f"SSH error: {exc}")
    except Exception as exc:
        logger.exception("Demo trigger failed for server %s", server.name)
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info("Demo trigger %s on %s: %s", anomaly_type, server.name, result)
    return {"status": "injected", "type": anomaly_type, "server": server.name, "ssh_output": result}

@router.post("/stop", summary="Stop all injected workloads and restore services")
async def stop_anomaly(
    server_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    server = await _get_server(db, server_id)
    if server.ssh_username == "sim":
        return {"status": "ok", "note": "synthetic server — nothing to stop via SSH"}

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _ssh_exec_sync, server, _STOP_CMD)
    except SSHConnectionError as exc:
        raise HTTPException(status_code=503, detail=f"SSH error: {exc}")

    return {"status": "stopped", "server": server.name}

@router.post("/run-ml", summary="Run ML analysis immediately for a server")
async def run_ml_now(
    server_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    server = await _get_server(db, server_id)
    try:
        anomalies = await MLPipeline.analyze(db, server)
    except Exception as exc:
        logger.exception("Demo run-ml failed for server %s", server.name)
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "anomalies_detected": len(anomalies),
        "anomaly_ids": [a.id for a in anomalies],
        "types": [a.anomaly_type for a in anomalies],
    }

@router.get("/status", summary="Demo environment overview")
async def demo_status(db: AsyncSession = Depends(get_db)) -> dict:
    servers = list((await db.execute(select(Server))).scalars().all())

    open_counts: dict[int, int] = {}
    if servers:
        rows = (
            await db.execute(
                select(Anomaly.server_id, func.count(Anomaly.id))
                .where(Anomaly.status == AnomalyStatus.OPEN.value)
                .group_by(Anomaly.server_id)
            )
        ).all()
        open_counts = {r[0]: r[1] for r in rows}

    latest_metrics: dict[int, str | None] = {}
    for srv in servers:
        snap = (
            await db.execute(
                select(MetricSnapshot.collected_at)
                .where(MetricSnapshot.server_id == srv.id)
                .order_by(MetricSnapshot.collected_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        latest_metrics[srv.id] = snap.isoformat() if snap else None

    return {
        "demo_mode": True,
        "servers": [
            {
                "id": s.id,
                "name": s.name,
                "host": s.host,
                "status": s.status,
                "synthetic": s.ssh_username == "sim",
                "open_anomalies": open_counts.get(s.id, 0),
                "latest_metric": latest_metrics.get(s.id),
            }
            for s in servers
        ],
    }
