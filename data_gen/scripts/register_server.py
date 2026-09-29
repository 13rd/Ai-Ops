#!/usr/bin/env python3

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.models.server import Server
from data_gen.db import SessionLocal

def main() -> None:
    parser = argparse.ArgumentParser(description="Register a testbed server in DB")
    parser.add_argument("--name", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", default=None)
    parser.add_argument("--private-key", default=None)
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--tags", nargs="*", default=[])
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing = db.query(Server).filter(Server.name == args.name).first()
        if existing:
            print(f"Server '{args.name}' already registered with id={existing.id}")
            return

        server = Server(
            name=args.name,
            host=args.host,
            port=args.port,
            ssh_username=args.username,
            ssh_password=args.password,
            ssh_private_key=args.private_key,
            environment=args.environment,
            tags=args.tags,
            status="offline",
        )
        db.add(server)
        db.commit()
        db.refresh(server)
        print(f"Registered server '{args.name}' with id={server.id}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
