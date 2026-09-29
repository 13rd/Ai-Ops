from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from data_gen.config import load_config

_config = load_config()

engine = create_engine(_config.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
