#!/usr/bin/env python3

import argparse
import json
import logging
import os
import signal
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from data_gen.scheduler.scenario_scheduler import ScenarioScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("run_scenario")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run anomaly scenario rotation")
    parser.add_argument("--config", required=True, help="Path to servers.json")
    parser.add_argument(
        "--server-ids",
        nargs="*",
        type=int,
        default=None,
        help="Restrict to specific server IDs (default: all)",
    )
    args = parser.parse_args()

    with open(args.config) as f:
        servers = json.load(f)

    if args.server_ids:
        servers = [s for s in servers if s["server_id"] in args.server_ids]

    scheduler = ScenarioScheduler()

    for s in servers:
        rotation = s.get("scenario_focus", "full")
        scheduler.add_server(
            server_id=s["server_id"],
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s.get("password"),
            private_key=s.get("private_key"),
            container_name=s.get("container_name", "test-app"),
            rotation=rotation,
        )
        logger.info(f"  server_id={s['server_id']} ({s['host']}:{s['port']}) → rotation={rotation}")

    def shutdown(sig, frame):  # type: ignore[no-untyped-def]
        logger.info("Stopping all scenario runners…")
        scheduler.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(f"Scenario rotation running for {len(servers)} server(s). Ctrl+C to stop.")
    import threading
    threading.Event().wait()

if __name__ == "__main__":
    main()
