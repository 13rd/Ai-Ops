from __future__ import annotations

import argparse
import asyncio
import logging
import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.models.anomaly import Anomaly, AnomalySeverity, AnomalyStatus
from app.models.notification import Notification
from app.models.recommendation import Recommendation
from app.models.server import Server
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("demo_seed")

HISTORY: list[tuple[str, int, str]] = [
    ("memory_leak",   48, AnomalySeverity.HIGH.value),
    ("disk_fill",     24, AnomalySeverity.MEDIUM.value),
    ("network_storm",  6, AnomalySeverity.MEDIUM.value),
]

_REC_TEMPLATES: dict[str, str] = {
    "memory_leak": (
        "Обнаружена утечка памяти. Рекомендуется:\n"
        "1. Выполнить `sudo systemctl restart app` для перезапуска приложения\n"
        "2. Проверить журналы: `journalctl -u app -n 100`\n"
        "3. Мониторить динамику: `free -m -s 5`"
    ),
    "disk_fill": (
        "Диск заполнен. Рекомендуется:\n"
        "1. Найти крупные файлы: `du -sh /var/log/* | sort -rh | head -10`\n"
        "2. Очистить логи: `sudo journalctl --vacuum-time=7d`\n"
        "3. Проверить /tmp: `du -sh /tmp`"
    ),
    "network_storm": (
        "Аномальный сетевой трафик. Рекомендуется:\n"
        "1. Проверить активные соединения: `ss -tunp | grep ESTABLISHED`\n"
        "2. Ограничить трафик: `sudo iptables -A INPUT -p tcp --dport 80 -m limit --limit 100/s`\n"
        "3. Анализировать источник: `tcpdump -i eth0 -c 100`"
    ),
}

_SHAP_TEMPLATES: dict[str, list[dict]] = {
    "memory_leak": [
        {"metric": "memory_usage_percent", "impact_percent": 72},
        {"metric": "swap_used_mb",          "impact_percent": 18},
        {"metric": "process_count",          "impact_percent": 10},
    ],
    "disk_fill": [
        {"metric": "disk_usage_percent",  "impact_percent": 81},
        {"metric": "disk_write_bytes",    "impact_percent": 12},
        {"metric": "disk_free_gb",        "impact_percent": 7},
    ],
    "network_storm": [
        {"metric": "network_in_bytes",     "impact_percent": 65},
        {"metric": "active_connections",   "impact_percent": 25},
        {"metric": "network_out_bytes",    "impact_percent": 10},
    ],
}

async def _get_server(db, name: str) -> Server:
    row = (await db.execute(select(Server).where(Server.name == name))).scalar_one_or_none()
    if row is None:
        raise SystemExit(f"Server '{name}' not found. Add it via UI first.")
    return row

async def _get_admin(db) -> User | None:
    result = await db.execute(
        select(User).where(User.role == UserRole.ADMIN.value, User.is_active.is_(True))
    )
    return result.scalars().first()

async def seed(server_name: str, dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        server = await _get_server(db, server_name)
        admin = await _get_admin(db)

        rng = random.Random(42)
        now = datetime.utcnow()

        for anomaly_type, hours_ago, severity in HISTORY:
            detected_at = now - timedelta(hours=hours_ago, minutes=rng.randint(0, 30))
            resolved_at = detected_at + timedelta(minutes=rng.randint(15, 45))

            anomaly = Anomaly(
                server_id=server.id,
                detected_at=detected_at,
                anomaly_type=anomaly_type,
                severity=severity,
                reconstruction_error=round(rng.uniform(0.35, 0.72), 4),
                threshold=0.25,
                shap_explanation=_SHAP_TEMPLATES.get(anomaly_type, []),
                metrics_snapshot={},
                status=AnomalyStatus.RESOLVED.value,
                resolved_at=resolved_at,
            )
            if not dry_run:
                db.add(anomaly)
                await db.flush()
                log.info(
                    "  + anomaly %-20s  %sh ago  (id=%d)", anomaly_type, hours_ago, anomaly.id
                )

                rec_text = _REC_TEMPLATES.get(anomaly_type, "Анализ завершён.")
                db.add(Recommendation(
                    anomaly_id=anomaly.id,
                    llm_raw_output=rec_text,
                    filtered_command=None,
                    explanation=rec_text,
                ))

                if admin:
                    atype_label = anomaly_type.replace("_", " ").title()
                    db.add(Notification(
                        user_id=admin.id,
                        title=f"[RESOLVED] {atype_label} on {server.name}",
                        body=f"Аномалия устранена через {rng.randint(15, 45)} мин.",
                        severity=severity,
                        anomaly_id=anomaly.id,
                        is_read=True,
                    ))
            else:
                log.info("  [dry] anomaly %-20s  %s ago", anomaly_type, f"{hours_ago}h")

        if not dry_run:
            await db.commit()
            log.info("Seeded %d historical anomalies for '%s'", len(HISTORY), server_name)
        else:
            log.info("Dry run complete — nothing written.")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-name", default="prod-web", help="Name of the demo target server")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(seed(args.server_name, args.dry_run))

if __name__ == "__main__":
    main()
