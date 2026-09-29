import os
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DataGenConfig:
    database_url: str
    collection_interval: int
    output_dir: str
    ssh_timeout: int

def _load_dotenv(path: str = ".env") -> dict:

    result: dict = {}
    p = Path(path)
    if not p.exists():
        return result
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result

def _to_sync_url(url: str) -> str:

    return url.replace("sqlite+aiosqlite", "sqlite").replace(
        "postgresql+asyncpg", "postgresql+psycopg2"
    )

def load_config() -> DataGenConfig:
    env = _load_dotenv(".env")

    if "DATAGEN_DATABASE_URL" in os.environ:
        db_url = os.environ["DATAGEN_DATABASE_URL"]
    elif "DATAGEN_DATABASE_URL" in env:
        db_url = env["DATAGEN_DATABASE_URL"]
    elif "DATABASE_URL" in os.environ:
        db_url = _to_sync_url(os.environ["DATABASE_URL"])
    elif "DATABASE_URL" in env:
        db_url = _to_sync_url(env["DATABASE_URL"])
    else:
        db_url = "postgresql+psycopg2://postgres:postgres@localhost:5432/server_monitor"

    return DataGenConfig(
        database_url=db_url,
        collection_interval=int(os.getenv("COLLECTION_INTERVAL", env.get("COLLECTION_INTERVAL", "15"))),
        output_dir=os.getenv("OUTPUT_DIR", "data_gen/output"),
        ssh_timeout=int(os.getenv("SSH_TIMEOUT", env.get("SSH_TIMEOUT", "10"))),
    )
