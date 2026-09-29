#!/usr/bin/env python3

import argparse
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from data_gen.db import SessionLocal
from data_gen.export.csv_exporter import CSVExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("export_dataset")

def export_one(server_id: int, mode: str, output: str, start: datetime | None, end: datetime | None) -> None:
    exporter = CSVExporter(server_id=server_id, output_dir=output)
    if mode == "rows":
        path = exporter.export_labeled_rows(start=start, end=end)
    else:
        path = exporter.export_windows(start=start, end=end)
    if path:
        print(f"  server_id={server_id}: {path}")
    else:
        print(f"  server_id={server_id}: no data found")

def main() -> None:
    parser = argparse.ArgumentParser(description="Export labeled training dataset")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server-id", type=int, help="Single server ID to export")
    group.add_argument("--all-servers", action="store_true", help="Export all servers in DB")
    parser.add_argument(
        "--mode", choices=["rows", "windows"], default="windows",
        help="rows=raw 15s timesteps, windows=300×5 sliding windows (default: windows)",
    )
    parser.add_argument("--output", default="data_gen/output", help="Output directory")
    parser.add_argument("--start", type=datetime.fromisoformat, default=None)
    parser.add_argument("--end", type=datetime.fromisoformat, default=None)
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    if args.server_id:
        server_ids = [args.server_id]
    else:
        from app.models.server import Server
        db = SessionLocal()
        try:
            server_ids = [s.id for s in db.query(Server).all()]
        finally:
            db.close()

    print(f"Exporting {len(server_ids)} server(s) in '{args.mode}' mode → {args.output}")
    for sid in server_ids:
        export_one(sid, args.mode, args.output, args.start, args.end)

if __name__ == "__main__":
    main()
