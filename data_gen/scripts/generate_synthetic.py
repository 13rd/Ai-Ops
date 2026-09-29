#!/usr/bin/env python3

import argparse
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from data_gen.db import SessionLocal
from data_gen.generators.synthetic import SyntheticNormalGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("generate_synthetic")

def generate_for(server_id: int, hours: int, start: datetime | None) -> None:
    gen = SyntheticNormalGenerator(server_id=server_id)
    rows = gen.generate(hours=hours, start_time=start)
    print(f"  server_id={server_id}: {rows} rows written ({hours}h of normal data)")

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic normal training data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server-id", type=int, help="Target server ID")
    group.add_argument("--all-servers", action="store_true", help="All servers in DB")
    parser.add_argument("--hours", type=int, default=24, help="Hours of data to generate (default: 24)")
    parser.add_argument(
        "--start",
        type=datetime.fromisoformat,
        default=None,
        help="Start timestamp ISO format (default: now - hours)",
    )
    args = parser.parse_args()

    if args.server_id:
        server_ids = [args.server_id]
    else:
        from app.models.server import Server
        db = SessionLocal()
        try:
            server_ids = [s.id for s in db.query(Server).all()]
        finally:
            db.close()

    print(f"Generating {args.hours}h synthetic normal data for {len(server_ids)} server(s)…")
    for sid in server_ids:
        generate_for(sid, args.hours, args.start)
    print("Done.")

if __name__ == "__main__":
    main()
