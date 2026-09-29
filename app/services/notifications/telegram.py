from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"
_TIMEOUT = 10.0

class TelegramSender:

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN)

    @staticmethod
    async def send(chat_id: str, text: str, *, parse_mode: str = "HTML") -> bool:

        if not TelegramSender.is_configured():
            logger.debug("Telegram skipped: TELEGRAM_BOT_TOKEN is not configured")
            return False
        if not chat_id:
            logger.warning("Telegram skipped: missing chat_id")
            return False

        url = f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                logger.warning(
                    "Telegram HTTP %s for chat %s: %s",
                    resp.status_code,
                    chat_id,
                    resp.text[:200],
                )
                return False
            body = resp.json() if resp.content else {}
            if not body.get("ok"):
                logger.warning("Telegram returned ok=false for chat %s: %s", chat_id, body)
                return False
            return True
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Telegram send failed for chat %s: %s", chat_id, exc)
            return False

def render_anomaly_message(
    *,
    server_name: str,
    server_host: Optional[str],
    anomaly_type: str,
    severity: str,
) -> str:
    location = server_host or "unknown host"
    return (
        f"<b>[{severity.upper()}] {anomaly_type.replace('_', ' ')}</b>\n"
        f"Server: <code>{server_name}</code> ({location})\n"
        f"Open the dashboard for details."
    )
