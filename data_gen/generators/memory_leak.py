import logging
import time
from typing import Any

from data_gen.generators.base import BaseGenerator

logger = logging.getLogger(__name__)

class MemoryLeakGenerator(BaseGenerator):

    scenario_type = "memory_leak"

    def run(
        self,
        duration_minutes: int = 25,
        leak_rate_mb_per_min: int = 180,
        **kwargs: Any,
    ) -> None:
        client = self._make_client()
        logger.info(f"[srv={self.server_id}] Memory leak scenario started ({duration_minutes} min)")
        try:
            for _ in range(20):
                self._ssh(client, "stress-ng --cpu 1 --cpu-load 20 --timeout 14s --quiet &")
                time.sleep(15)

            total_ram_mb = int(
                self._ssh(client, "free -m | awk 'NR==2{print $2}'") or "4096"
            )
            self._open_event(
                {
                    "leak_rate_mb_per_min": leak_rate_mb_per_min,
                    "total_memory_mb": total_ram_mb,
                }
            )

            leak_minutes = duration_minutes - 10
            step_alloc = leak_rate_mb_per_min // 4
            allocated_mb = int(total_ram_mb * 0.3)

            for _ in range(leak_minutes * 4):
                allocated_mb = min(allocated_mb + step_alloc, int(total_ram_mb * 0.92))
                self._ssh(
                    client,
                    f"stress-ng --vm 1 --vm-bytes {allocated_mb}M --vm-keep "
                    f"--timeout 14s --quiet &",
                )
                time.sleep(15)

            for _ in range(20):
                time.sleep(15)

            peak_mem = int(
                self._ssh(client, "free -m | awk 'NR==2{print $3}'") or "0"
            )
            self._close_event(
                {
                    "peak_memory_mb": peak_mem,
                    "peak_memory_percent": round(peak_mem / total_ram_mb * 100, 1),
                }
            )
        finally:
            self._ssh(client, "pkill stress-ng 2>/dev/null || true")
            client.close()
        logger.info(f"[srv={self.server_id}] Memory leak scenario finished")
