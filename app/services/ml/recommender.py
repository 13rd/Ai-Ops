"""Stub recommender.

Real implementation feeds anomaly + SHAP context to an LLM with a strict
filtering pipeline. This stub:

- maps each anomaly_type to a predefined safe diagnostic command;
- runs *every* candidate command through is_command_safe() to enforce the
  same allow-list contract the real recommender will use;
- never emits anything that mutates the filesystem or shuts services down.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.models.anomaly import AnomalyType

logger = logging.getLogger(__name__)


@dataclass
class RecommendationDraft:
    filtered_command: str
    explanation: str
    llm_raw_output: str | None = None


# Mutating / destructive patterns. The list is intentionally minimal and
# defensive — drop into deny mode on any match. Update with care; the unit
# test suite exercises specific examples.
_DANGEROUS_PATTERNS = [
    r"\brm\s+-rf?\b",
    r"\bdd\s+if=",
    r"\bmkfs(\.|\s)",
    r":\(\)\s*\{\s*:\|:&\s*\};:",  # classic fork-bomb signature
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


def is_command_safe(command: str) -> bool:
    """Return False if `command` matches a known-dangerous pattern."""
    if not command or not command.strip():
        return False
    lowered = command.lower()
    return not any(re.search(p, lowered) for p in _DANGEROUS_PATTERNS)


_TEMPLATES: dict[str, RecommendationDraft] = {
    AnomalyType.CPU_SPIKE.value: RecommendationDraft(
        filtered_command="ps -eo pid,pcpu,pmem,comm --sort=-pcpu | head -n 10",
        explanation=(
            "CPU load is sustained above the threshold. Inspect the top CPU consumers "
            "before taking any remediation action — a misbehaving process or runaway "
            "thread is the usual cause."
        ),
    ),
    AnomalyType.MEMORY_LEAK.value: RecommendationDraft(
        filtered_command="ps -eo pid,pmem,rss,comm --sort=-rss | head -n 10",
        explanation=(
            "Memory utilisation is approaching capacity with no expected workload "
            "spike. Identify the highest-RSS processes; a growing footprint over time "
            "indicates a leak that warrants a controlled restart of the affected service."
        ),
    ),
    AnomalyType.CONTAINER_CRASH.value: RecommendationDraft(
        filtered_command=(
            "docker ps -a --format 'table {{.Names}}\\t{{.Status}}\\t{{.RestartCount}}'"
        ),
        explanation=(
            "One or more containers show repeated restarts. Review their exit codes "
            "and recent logs before approving any automated restart."
        ),
    ),
    AnomalyType.SERVICE_DOWN.value: RecommendationDraft(
        filtered_command="systemctl --failed; uptime",
        explanation=(
            "The server is unreachable or has failed services. Confirm host reachability "
            "and failed unit list before scheduling a recovery action."
        ),
    ),
    AnomalyType.DISK_PRESSURE.value: RecommendationDraft(
        filtered_command="df -h; du -hx --max-depth=1 / | sort -h | tail -n 10",
        explanation=(
            "Disk usage is above the safe ceiling. Identify the largest directories "
            "to plan archival or eviction; no destructive cleanup is recommended "
            "automatically."
        ),
    ),
    AnomalyType.NETWORK_ANOMALY.value: RecommendationDraft(
        filtered_command="ss -s; ip -s link",
        explanation=(
            "Unusual network counters detected. Capture socket statistics and "
            "interface error counters for further investigation."
        ),
    ),
}


_FALLBACK = RecommendationDraft(
    filtered_command="uptime; dmesg | tail -n 50",
    explanation="No type-specific playbook available. Collect general health signals.",
)


class Recommender:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_sec: int | None = None,
    ):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.timeout_sec = timeout_sec or settings.OLLAMA_TIMEOUT_SEC

    @staticmethod
    def recommend(anomaly_type: str) -> RecommendationDraft:
        """Synchronous template lookup (used by rule-based fallback)."""
        draft = _TEMPLATES.get(anomaly_type, _FALLBACK)
        if not is_command_safe(draft.filtered_command):
            return RecommendationDraft(
                filtered_command="",
                explanation=(
                    "Recommendation suppressed: candidate command failed the safety "
                    "filter and requires manual review."
                ),
            )
        return draft

    async def _call_ollama(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            r = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            return r.json().get("response", "")

    async def recommend_async(
        self, anomaly_type: str, top_features: list[dict] | None = None,
    ) -> RecommendationDraft:
        """Async Ollama-backed recommendation with template fallback."""
        prompt = (
            "You are a senior sysadmin. Respond with two blocks only:\n"
            "EXPLANATION: <one sentence>\n"
            "COMMAND: <single read-only shell command, no destructive ops>\n\n"
            f"Anomaly type: {anomaly_type}\n"
            f"Top features: {(top_features or [])[:3]}\n"
        )
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
                explanation=expl or "Ollama recommendation",
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
