from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.models.anomaly import AnomalyType
from app.models.llm_settings import LLMSettings

logger = logging.getLogger(__name__)

@dataclass
class RecommendationDraft:
    filtered_command: str
    explanation: str
    llm_raw_output: str | None = None

_DANGEROUS_PATTERNS = [
    r"\brm\s+-rf?\b",
    r"\bdd\s+if=",
    r"\bmkfs(\.|\s)",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bpoweroff\b",
    r"\bchmod\s+777\s+/",
    r"\bchown\s+.+\s+/",
    r"\bnc\s+.+\|\s*sh\b",
    r">\s*/dev/sd",
    r">\s*/etc/",
    r"\bcurl\b.+\|\s*(sh|bash)\b",
    r"\bwget\b.+\|\s*(sh|bash)\b",
]

_ALLOWED_BINARIES = frozenset(
    {
        "ps", "top", "htop", "uptime", "free", "vmstat", "iostat", "mpstat",
        "df", "du", "lsblk", "stat", "ls", "find",
        "ss", "ip", "netstat", "ping", "ssh",
        "systemctl", "journalctl", "service",
        "docker", "kubectl",
        "cat", "head", "tail", "grep", "egrep", "awk", "sort", "uniq", "wc",
        "dmesg", "who", "w", "lsof", "uname", "date", "echo",
    }
)

_SEGMENT_SPLIT = re.compile(r"[;|]|&&|\|\|")

def _segment_leading_tokens(command: str) -> list[str]:

    tokens: list[str] = []
    for segment in _SEGMENT_SPLIT.split(command):
        parts = segment.strip().split()
        if not parts:
            continue
        head = parts[0]
        if head == "sudo" and len(parts) > 1:
            head = parts[1]
        tokens.append(head.rsplit("/", 1)[-1])
    return tokens

def is_command_safe(command: str) -> bool:

    if not command or not command.strip():
        return False
    lowered = command.lower()
    if any(re.search(p, lowered) for p in _DANGEROUS_PATTERNS):
        return False
    leading = _segment_leading_tokens(command)
    if not leading:
        return False
    return all(tok in _ALLOWED_BINARIES for tok in leading)

_TEMPLATES: dict[str, RecommendationDraft] = {
    AnomalyType.CPU_SPIKE.value: RecommendationDraft(
        filtered_command="ps -eo pid,pcpu,pmem,comm --sort=-pcpu | head -n 10",
        explanation=(
            "Нагрузка на CPU устойчиво превышает порог. Прежде чем предпринимать "
            "какие-либо действия, изучите процессы — основные потребители CPU: "
            "обычная причина — сбойный процесс или зациклившийся поток."
        ),
    ),
    AnomalyType.MEMORY_LEAK.value: RecommendationDraft(
        filtered_command="ps -eo pid,pmem,rss,comm --sort=-rss | head -n 10",
        explanation=(
            "Использование памяти приближается к пределу без ожидаемого роста "
            "нагрузки. Определите процессы с наибольшим RSS; постепенно растущий "
            "объём указывает на утечку и требует контролируемого перезапуска службы."
        ),
    ),
    AnomalyType.CONTAINER_CRASH.value: RecommendationDraft(
        filtered_command=(
            "docker ps -a --format 'table {{.Names}}\\t{{.Status}}\\t{{.RestartCount}}'"
        ),
        explanation=(
            "Один или несколько контейнеров постоянно перезапускаются. Проверьте их "
            "коды выхода и последние логи, прежде чем одобрять автоматический перезапуск."
        ),
    ),
    AnomalyType.SERVICE_DOWN.value: RecommendationDraft(
        filtered_command="systemctl --failed; uptime",
        explanation=(
            "Сервер недоступен или есть упавшие службы. Подтвердите доступность хоста "
            "и список упавших юнитов перед планированием восстановления."
        ),
    ),
    AnomalyType.DISK_PRESSURE.value: RecommendationDraft(
        filtered_command="df -h; du -hx --max-depth=1 / | sort -h | tail -n 10",
        explanation=(
            "Использование диска выше безопасного предела. Определите крупнейшие "
            "каталоги для планирования архивации или очистки; автоматическая "
            "деструктивная очистка не рекомендуется."
        ),
    ),
    AnomalyType.NETWORK_ANOMALY.value: RecommendationDraft(
        filtered_command="ss -s; ip -s link",
        explanation=(
            "Обнаружены необычные сетевые показатели. Снимите статистику сокетов и "
            "счётчики ошибок интерфейсов для дальнейшего анализа."
        ),
    ),
    AnomalyType.DISK_FILL.value: RecommendationDraft(
        filtered_command="df -h; du -hx --max-depth=2 / | sort -h | tail -n 15",
        explanation=(
            "Свободное место на диске быстро расходуется. Найдите наиболее быстро "
            "растущие каталоги до любой очистки; не удаляйте файлы автоматически."
        ),
    ),
    AnomalyType.NETWORK_STORM.value: RecommendationDraft(
        filtered_command="ss -s; ip -s link; ss -tunap | head -n 20",
        explanation=(
            "Идёт всплеск трафика или шторм соединений. Снимите агрегированную "
            "статистику сокетов, счётчики ошибок интерфейсов и самые активные сокеты."
        ),
    ),
}

_FALLBACK = RecommendationDraft(
    filtered_command="uptime; dmesg | tail -n 50",
    explanation=(
        "Специализированный сценарий для этого типа отсутствует. "
        "Соберите общие показатели состояния системы."
    ),
)

DEFAULT_PROMPT_TEMPLATE = (
    "Ты — старший системный администратор. Отвечай только на русском языке.\n"
    "Сформируй ответ строго в виде двух блоков и не добавляй ничего лишнего:\n"
    "EXPLANATION: <одно ёмкое предложение, учитывающее конкретику инцидента ниже>\n"
    "COMMAND: <одна безопасная команда только для чтения — диагностика, без изменения системы>\n"
    "\n"
    "Контекст инцидента:\n"
    "- Тип аномалии: {anomaly_type}\n"
    "- Серьёзность: {severity}\n"
    "- Сервер: {server_name} (окружение: {environment})\n"
    "- Текущие значения метрик: {metrics_summary}\n"
    "- Наиболее значимые признаки (вклад в обнаружение): {top_features}\n"
    "- Похожие случаи ранее: {history_summary}\n"
)

_DEFAULT_PROMPT_CONTEXT: dict[str, str] = {
    "severity": "неизвестна",
    "server_name": "неизвестен",
    "environment": "не указано",
    "metrics_summary": "нет данных",
    "top_features": "нет данных",
    "history_summary": "нет данных",
}

class Recommender:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_sec: int | None = None,
        keep_alive: str | None = None,
        prompt_template: str | None = None,
    ):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.timeout_sec = timeout_sec or settings.OLLAMA_TIMEOUT_SEC
        self.keep_alive = keep_alive or settings.OLLAMA_KEEP_ALIVE
        self.prompt_template = prompt_template or DEFAULT_PROMPT_TEMPLATE

    @classmethod
    def from_settings(cls, db_settings: LLMSettings | None) -> "Recommender":

        if db_settings is None:
            return cls()
        return cls(
            model=db_settings.model,
            timeout_sec=db_settings.timeout_sec,
            keep_alive=db_settings.keep_alive,
            prompt_template=db_settings.prompt_template,
        )

    @staticmethod
    def recommend(anomaly_type: str) -> RecommendationDraft:

        draft = _TEMPLATES.get(anomaly_type, _FALLBACK)
        if not is_command_safe(draft.filtered_command):
            return RecommendationDraft(
                filtered_command="",
                explanation=(
                    "Рекомендация подавлена: команда-кандидат не прошла фильтр "
                    "безопасности и требует ручной проверки."
                ),
            )
        return draft

    async def _call_ollama(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            r = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": self.keep_alive,
                },
            )
            r.raise_for_status()
            return r.json().get("response", "")

    async def recommend_async(
        self, anomaly_type: str, context: dict[str, str] | None = None,
    ) -> RecommendationDraft:

        ctx = {"anomaly_type": anomaly_type, **_DEFAULT_PROMPT_CONTEXT, **(context or {})}
        try:
            prompt = self.prompt_template.format(**ctx)
        except (KeyError, IndexError, ValueError):
            logger.warning("Invalid prompt_template for %s; using default", anomaly_type)
            prompt = DEFAULT_PROMPT_TEMPLATE.format(**ctx)
        try:
            text = await self._call_ollama(prompt)
            expl = _extract_block("EXPLANATION", text)
            cmd = _extract_block("COMMAND", text)
            if not cmd or not is_command_safe(cmd):
                logger.info(
                    "Ollama returned unsafe/empty command for %s, falling back",
                    anomaly_type,
                )
                return self.recommend(anomaly_type)
            return RecommendationDraft(
                filtered_command=cmd,
                explanation=expl or "Рекомендация сформирована Ollama.",
                llm_raw_output=text,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ollama call failed (%s); using template", exc)
            return self.recommend(anomaly_type)

def _extract_block(key: str, text: str) -> str:
    for line in (text or "").splitlines():
        if line.upper().startswith(key.upper()):
            return line.split(":", 1)[-1].strip().strip("`").strip()
    return ""
