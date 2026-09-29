#!/usr/bin/env python3

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

import paramiko

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.models.anomaly_event import AnomalyEvent
from app.models.server import Server
from data_gen.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("inject_anomalies")

INJECT_CMDS: dict[str, str] = {
    "cpu_spike": (
        "nohup sudo stress-ng --cpu 0 --timeout {dur}s >/dev/null 2>&1 </dev/null &"
    ),
    "memory_leak": (
        "nohup sudo stress-ng --vm 1 --vm-bytes 80% --timeout {dur}s "
        ">/dev/null 2>&1 </dev/null &"
    ),
    "disk_fill": (
        "nohup sudo dd if=/dev/zero of=/tmp/anom_fill bs=1M count=4096 "
        ">/dev/null 2>&1 </dev/null &"
    ),
    "network_storm": (
        "nohup sudo stress-ng --sock 4 --udp 4 --timeout {dur}s "
        ">/dev/null 2>&1 </dev/null &"
    ),
    "container_crash": (
        "sudo docker kill $(sudo docker ps -q | head -1) 2>/dev/null || true"
    ),
    "service_down": "sudo systemctl stop nginx 2>/dev/null || true",
}

STOP_CMD = (
    "sudo pkill -f stress-ng 2>/dev/null; "
    "sudo systemctl start nginx 2>/dev/null; "
    "sudo rm -f /tmp/anom_fill* 2>/dev/null; "
    "echo done"
)

TESTBED_INJECT_CMDS: dict[str, str] = {t: f"sudo anomaly {t} {{dur}}" for t in INJECT_CMDS}
TESTBED_STOP_CMD = "sudo anomaly stop"

def _command_set(server: dict) -> tuple[dict[str, str], str]:

    if server.get("inject_mode") == "testbed":
        return TESTBED_INJECT_CMDS, TESTBED_STOP_CMD
    return INJECT_CMDS, STOP_CMD

def _make_client(server: dict) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict = {
        "hostname": server["host"],
        "port": server.get("port", 22),
        "username": server["username"],
        "timeout": 10,
        "look_for_keys": False,
        "allow_agent": False,
    }
    if server.get("password"):
        kwargs["password"] = server["password"]
    elif server.get("private_key_path"):
        key_path = os.path.expanduser(server["private_key_path"])
        kwargs["pkey"] = paramiko.RSAKey.from_private_key_file(key_path)
    elif server.get("private_key"):
        from io import StringIO
        kwargs["pkey"] = paramiko.RSAKey.from_private_key(StringIO(server["private_key"]))
    client.connect(**kwargs)
    return client

def _ssh_exec(server: dict, cmd: str) -> str:
    client = _make_client(server)
    try:
        _stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        return out or err
    finally:
        client.close()

def _resolve_server_id(name: str, fallback: int | None) -> int | None:

    db = SessionLocal()
    try:
        srv = db.query(Server).filter(Server.name == name).first()
        if srv:
            return srv.id
    finally:
        db.close()
    return fallback

def _build_schedule(inject_list: list[str], episodes: int) -> list[str]:

    types = [t for t in inject_list if t in INJECT_CMDS]
    unknown = [t for t in inject_list if t not in INJECT_CMDS]
    if unknown:
        logger.warning("ignoring unknown anomaly types: %s", unknown)
    schedule: list[str] = []
    for _ in range(episodes):
        schedule.extend(types)
    return schedule

def _write_event_start(server_id: int, atype: str, start: datetime) -> int:
    db = SessionLocal()
    try:
        ev = AnomalyEvent(
            server_id=server_id,
            scenario_type=atype,
            start_ts=start,
            end_ts=None,
            parameters={"source": "inject_anomalies"},
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        return ev.id
    finally:
        db.close()

def _write_event_end(event_id: int, end: datetime) -> None:
    db = SessionLocal()
    try:
        ev = db.get(AnomalyEvent, event_id)
        if ev:
            ev.end_ts = end
            db.commit()
    finally:
        db.close()

def _run_episode(
    server: dict, server_id: int, atype: str, duration: int,
    inject_cmds: dict[str, str], stop_cmd: str,
) -> None:
    start = datetime.utcnow()
    event_id = _write_event_start(server_id, atype, start)
    logger.info("[%s] START %s (event_id=%d, %ds)", server["name"], atype, event_id, duration)
    try:
        out = _ssh_exec(server, inject_cmds[atype].format(dur=duration))
        if out:
            logger.debug("[%s] inject output: %s", server["name"], out)
        time.sleep(duration)
    finally:
        _ssh_exec(server, stop_cmd)
        _write_event_end(event_id, datetime.utcnow())
        logger.info("[%s] END   %s (event_id=%d)", server["name"], atype, event_id)

def main() -> None:
    ap = argparse.ArgumentParser(description="Inject all anomaly types over SSH + label them")
    ap.add_argument("--config", required=True, help="Path to real_servers.json")
    ap.add_argument("--episodes", type=int, default=5,
                    help="Episodes per anomaly type, per server (default 5)")
    ap.add_argument("--duration", type=int, default=120,
                    help="Seconds each anomaly stays active (default 120)")
    ap.add_argument("--pause", type=int, default=60,
                    help="Recovery seconds between episodes (default 60)")
    ap.add_argument("--server", default=None,
                    help="Only inject on this server name (default: all role=anomaly)")
    args = ap.parse_args()

    with open(args.config) as f:
        servers = json.load(f)

    targets = [
        s for s in servers
        if s.get("role") == "anomaly" and (args.server is None or s["name"] == args.server)
    ]
    if not targets:
        logger.error("No anomaly-role servers matched in %s", args.config)
        sys.exit(1)

    for server in targets:
        server_id = _resolve_server_id(server["name"], server.get("server_id"))
        if server_id is None:
            logger.error("[%s] not registered (run register_server.py first); skipping",
                         server["name"])
            continue
        schedule = _build_schedule(server.get("inject_anomalies", []), args.episodes)
        if not schedule:
            logger.warning("[%s] empty inject_anomalies; skipping", server["name"])
            continue
        inject_cmds, stop_cmd = _command_set(server)
        logger.info("[%s] %d episodes across %d types (mode=%s, ~%dmin)",
                    server["name"], len(schedule), len(set(schedule)),
                    server.get("inject_mode", "vm"),
                    len(schedule) * (args.duration + args.pause) // 60)
        for idx, atype in enumerate(schedule):
            _run_episode(server, server_id, atype, args.duration, inject_cmds, stop_cmd)
            if idx < len(schedule) - 1:
                logger.info("[%s] recovery pause %ds", server["name"], args.pause)
                time.sleep(args.pause)

    logger.info("Injection complete. Re-run prepare_dataset to pick up the new labels.")

if __name__ == "__main__":
    main()
