import logging
import time
from typing import Any

from data_gen.generators.base import BaseGenerator

logger = logging.getLogger(__name__)

class ContainerCrashGenerator(BaseGenerator):

    scenario_type = "container_crash"

    def run(
        self,
        container_name: str = "test-app",
        normal_min: int = 5,
        down_min: int = 5,
        recovery_min: int = 3,
        **kwargs: Any,
    ) -> None:
        client = self._make_client()
        logger.info(
            f"[srv={self.server_id}] Container crash scenario started "
            f"(container={container_name})"
        )
        try:
            time.sleep(normal_min * 60)

            self._open_event({"container_name": container_name, "kill_signal": "SIGKILL"})

            self._ssh(client, f"docker kill {container_name} 2>/dev/null || true")
            time.sleep(down_min * 60)

            self._ssh(client, f"docker start {container_name} 2>/dev/null || true")
            self._close_event({"restart_attempted": True})

            time.sleep(recovery_min * 60)
        finally:
            client.close()
        logger.info(f"[srv={self.server_id}] Container crash scenario finished")
