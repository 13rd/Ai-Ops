from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    APP_NAME: str = "Server Monitor Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database (default to SQLite for local dev)
    DATABASE_URL: str = "sqlite+aiosqlite:///./server_monitor.db"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # SSH Connection
    SSH_TIMEOUT: int = 10  # seconds
    SSH_CONNECTION_RETRIES: int = 3

    # Metrics Collection
    METRICS_COLLECTION_INTERVAL: int = 60  # seconds
    METRICS_RETENTION_DAYS: int = 30

    # TODO: Add vault integration for credentials storage
    # VAULT_URL: str = ""
    # VAULT_TOKEN: str = ""


settings = Settings()
