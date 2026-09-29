#!/usr/bin/env python3

import argparse
import json
import logging
import os
import signal
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from data_gen.collectors.ssh_collector import SSHCollector
from data_gen.db import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("run_collector")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run SSH metric collectors")
    parser.add_argument("--config", required=True, help="Path to servers.json")
    parser.add_argument("--interval", type=int, default=15, help="Collection interval in seconds")
    args = parser.parse_args()

    with open(args.config) as f:
        servers = json.load(f)

    collectors: list[SSHCollector] = []
    threads: list[threading.Thread] = []

    for s in servers:
        private_key = s.get("private_key")
        if not private_key and s.get("private_key_path"):
            private_key = os.path.expanduser(s["private_key_path"])
            with open(private_key) as kf:
                private_key = kf.read()
        c = SSHCollector(
            server_id=s["server_id"],
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s.get("password"),
            private_key=private_key,
            db_session_factory=SessionLocal,
            interval=args.interval,
        )
        collectors.append(c)
        t = threading.Thread(
            target=c.run,
            daemon=True,
            name=f"collector-{s['server_id']}",
        )
        t.start()
        threads.append(t)
        logger.info(f"Started collector for server_id={s['server_id']} ({s['host']}:{s['port']})")

    def shutdown(sig, frame):  # type: ignore[no-untyped-def]
        logger.info("Shutting down collectors…")
        for col in collectors:
            col.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(f"Collecting from {len(servers)} server(s) every {args.interval}s. Ctrl+C to stop.")
    for t in threads:
        t.join()

if __name__ == "__main__":
    main()
