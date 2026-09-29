from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Server Monitor Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./server_monitor.db"

    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    SSH_ENCRYPTION_KEY: str = "dev-only-change-this-fernet-master-key"

    SSH_TIMEOUT: int = 10
    SSH_CONNECTION_RETRIES: int = 3

    METRICS_COLLECTION_INTERVAL: int = 60
    METRICS_INTERVAL_SEC: int = 15
    METRICS_RETENTION_DAYS: int = 30

    ML_INTERVAL_MIN: int = 5
    ML_MODELS_DIR: str = "models"
    ML_INFERENCE_INTERVAL_SEC: int = 60
    ML_WINDOW_SIZE: int = 60
    ML_BACKGROUND_SET_SIZE: int = 100
    ML_ANOMALY_MAX_OPEN_MIN: int = 30
    ML_ANOMALY_DEDUP_GRACE_MIN: int = 5
    ML_DEMO_DISABLE_DEDUP: bool = False
    ML_CORROBORATION_MIN_PERCENT: float = 80.0

    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_TIMEOUT_SEC: int = 60
    OLLAMA_KEEP_ALIVE: str = "30m"

    AUDIT_LOG_RETENTION_DAYS: int = 180

    REDIS_URL: str = "redis://localhost:6379/0"

    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_DEFAULT_CHAT_ID: Optional[str] = None

    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_CORS_ORIGINS: str = "*"

    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    DEMO_MODE: bool = False

settings = Settings()
