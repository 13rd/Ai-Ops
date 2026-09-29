import logging
import time
from typing import Any

from data_gen.generators.base import BaseGenerator

logger = logging.getLogger(__name__)

class ServiceDownGenerator(BaseGenerator):

    scenario_type = "service_down"

    def run(
        self,
        iface: str = "eth0",
        normal_min: int = 5,
        fail_min: int = 7,
        recovery_min: int = 3,
        delay_ms: int = 500,
        packet_loss_pct: int = 30,
        **kwargs: Any,
    ) -> None:
        client = self._make_client()
        logger.info(f"[srv={self.server_id}] Service down scenario started (iface={iface})")
        try:
            time.sleep(normal_min * 60)

            self._open_event(
                {
                    "interface": iface,
                    "delay_ms": delay_ms,
                    "packet_loss_pct": packet_loss_pct,
                }
            )

            half = fail_min // 2

            self._ssh(
                client,
                f"tc qdisc add dev {iface} root netem delay {delay_ms}ms 2>/dev/null "
                f"|| tc qdisc change dev {iface} root netem delay {delay_ms}ms",
            )
            time.sleep(half * 60)

            self._ssh(
                client,
                f"tc qdisc change dev {iface} root netem "
                f"delay {delay_ms}ms loss {packet_loss_pct}%",
            )
            time.sleep((fail_min - half) * 60)

            self._ssh(client, f"tc qdisc del dev {iface} root 2>/dev/null || true")
            self._close_event({"recovery": "tc_restored"})

            time.sleep(recovery_min * 60)
        finally:
            self._ssh(client, f"tc qdisc del dev {iface} root 2>/dev/null || true")
            client.close()
        logger.info(f"[srv={self.server_id}] Service down scenario finished")
