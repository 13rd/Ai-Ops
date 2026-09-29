from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisClient:

    def __init__(self, url: Optional[str]) -> None:
        self._url = url or ""
        self._client: Optional[redis.Redis] = None
        self._healthy = False
        self._init_attempted = False

    async def _ensure(self) -> Optional[redis.Redis]:
        if not self._url:
            return None
        if self._client is not None:
            return self._client if self._healthy else None
        if self._init_attempted:
            return None
        self._init_attempted = True
        try:
            client = redis.from_url(self._url, decode_responses=True)
            await client.ping()
            self._client = client
            self._healthy = True
            logger.info("Redis connected at %s", _redact(self._url))
            return client
        except (RedisError, OSError) as exc:
            logger.warning("Redis unavailable at %s: %s — running in no-op mode",
                           _redact(self._url), exc)
            self._healthy = False
            return None

    async def get_json(self, key: str) -> Optional[Any]:
        client = await self._ensure()
        if client is None:
            return None
        try:
            raw = await client.get(key)
            return json.loads(raw) if raw is not None else None
        except (RedisError, json.JSONDecodeError) as exc:
            logger.warning("Redis GET %s failed: %s", key, exc)
            return None

    async def set_json(self, key: str, value: Any, *, ttl: Optional[int] = None) -> bool:
        client = await self._ensure()
        if client is None:
            return False
        try:
            payload = json.dumps(value, default=str)
            await client.set(key, payload, ex=ttl)
            return True
        except RedisError as exc:
            logger.warning("Redis SET %s failed: %s", key, exc)
            return False

    async def delete(self, key: str) -> bool:
        client = await self._ensure()
        if client is None:
            return False
        try:
            await client.delete(key)
            return True
        except RedisError as exc:
            logger.warning("Redis DEL %s failed: %s", key, exc)
            return False

    async def publish(self, channel: str, message: Any) -> int:
        client = await self._ensure()
        if client is None:
            return 0
        try:
            payload = json.dumps(message, default=str) if not isinstance(message, str) else message
            return int(await client.publish(channel, payload))
        except RedisError as exc:
            logger.warning("Redis PUBLISH %s failed: %s", channel, exc)
            return 0

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except RedisError:
                pass

def _redact(url: str) -> str:

    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1) if "://" in url else ("redis", url)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        creds = f"{user}:***"
    return f"{scheme}://{creds}@{host}"

_singleton: Optional[RedisClient] = None

def get_redis_client() -> RedisClient:
    global _singleton
    if _singleton is None:
        _singleton = RedisClient(settings.REDIS_URL)
    return _singleton

async def reset_redis_client_for_tests() -> None:

    global _singleton
    if _singleton is not None:
        await _singleton.close()
    _singleton = None
