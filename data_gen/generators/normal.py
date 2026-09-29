import logging
import random
import time
from typing import Any

from data_gen.generators.base import BaseGenerator

logger = logging.getLogger(__name__)

class NormalGenerator(BaseGenerator):

    scenario_type = "normal"

    def run(self, duration_minutes: int = 60, **kwargs: Any) -> None:
        client = self._make_client()
        logger.info(f"[srv={self.server_id}] Normal scenario started ({duration_minutes} min)")
        try:
            total_steps = duration_minutes * 4
            for _ in range(total_steps):
                cpu_pct = random.randint(10, 40)
                self._ssh(
                    client,
                    f"stress-ng --cpu 1 --cpu-load {cpu_pct} --timeout 14s --quiet &",
                )
                time.sleep(15)
        finally:
            self._ssh(client, "pkill stress-ng 2>/dev/null || true")
            client.close()
        logger.info(f"[srv={self.server_id}] Normal scenario finished")
