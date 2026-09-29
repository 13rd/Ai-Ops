import logging
import time
from typing import Any

from data_gen.generators.base import BaseGenerator

logger = logging.getLogger(__name__)

class CPUSpikeGenerator(BaseGenerator):

    scenario_type = "cpu_spike"

    def run(
        self,
        normal_min: int = 3,
        spike_min: int = 5,
        aftermath_min: int = 3,
        **kwargs: Any,
    ) -> None:
        client = self._make_client()
        logger.info(f"[srv={self.server_id}] CPU spike scenario started")
        try:
            ncpus = int(self._ssh(client, "nproc") or "1")

            for _ in range(normal_min * 4):
                self._ssh(client, "stress-ng --cpu 1 --cpu-load 20 --timeout 14s --quiet &")
                time.sleep(15)

            self._open_event({"target_cpu_cores": ncpus, "spike_duration_min": spike_min})

            self._ssh(
                client,
                f"stress-ng --cpu {ncpus} --timeout {spike_min * 60}s --quiet &",
            )
            time.sleep(spike_min * 60)
            self._ssh(client, "pkill stress-ng 2>/dev/null || true")
            self._close_event({"actual_ncpus": ncpus})

            time.sleep(aftermath_min * 60)
        finally:
            self._ssh(client, "pkill stress-ng 2>/dev/null || true")
            client.close()
        logger.info(f"[srv={self.server_id}] CPU spike scenario finished")
