import logging
import threading
from typing import Any, Dict, List, Optional, Tuple, Type

from data_gen.generators.base import BaseGenerator
from data_gen.generators.container_crash import ContainerCrashGenerator
from data_gen.generators.cpu_spike import CPUSpikeGenerator
from data_gen.generators.memory_leak import MemoryLeakGenerator
from data_gen.generators.normal import NormalGenerator
from data_gen.generators.service_down import ServiceDownGenerator

logger = logging.getLogger(__name__)

RotationList = List[Tuple[Type[BaseGenerator], Dict[str, Any]]]

SCENARIO_ROTATION: RotationList = [
    (NormalGenerator, {"duration_minutes": 60}),
    (MemoryLeakGenerator, {"duration_minutes": 25}),
    (NormalGenerator, {"duration_minutes": 60}),
    (CPUSpikeGenerator, {"normal_min": 3, "spike_min": 5, "aftermath_min": 3}),
    (NormalGenerator, {"duration_minutes": 60}),
    (ContainerCrashGenerator, {"normal_min": 5, "down_min": 5, "recovery_min": 3}),
    (NormalGenerator, {"duration_minutes": 60}),
    (ServiceDownGenerator, {"normal_min": 5, "fail_min": 7, "recovery_min": 3}),
]

ROTATIONS: Dict[str, RotationList] = {
    "normal_cpu": [
        (NormalGenerator, {"duration_minutes": 10}),
        (CPUSpikeGenerator, {"normal_min": 2, "spike_min": 5, "aftermath_min": 2}),
    ],
    "memory_crash": [
        (MemoryLeakGenerator, {"duration_minutes": 20}),
        (NormalGenerator, {"duration_minutes": 10}),
        (ContainerCrashGenerator, {"normal_min": 3, "down_min": 5, "recovery_min": 2}),
        (NormalGenerator, {"duration_minutes": 10}),
    ],
    "service_down": [
        (ServiceDownGenerator, {"normal_min": 3, "fail_min": 7, "recovery_min": 3}),
        (NormalGenerator, {"duration_minutes": 10}),
    ],
    "full": SCENARIO_ROTATION,
}

class ServerScenarioRunner:

    def __init__(
        self,
        server_id: int,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        container_name: str = "test-app",
        rotation: Optional[RotationList] = None,
    ) -> None:
        self.server_id = server_id
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.container_name = container_name
        self._rotation = rotation if rotation is not None else SCENARIO_ROTATION
        self._stop_event = threading.Event()

    def run(self) -> None:
        cycle = 0
        while not self._stop_event.is_set():
            logger.info(f"[srv={self.server_id}] Starting rotation cycle {cycle}")
            for GenClass, kwargs in self._rotation:
                if self._stop_event.is_set():
                    break
                effective_kwargs = (
                    {**kwargs, "container_name": self.container_name}
                    if GenClass is ContainerCrashGenerator
                    else dict(kwargs)
                )
                gen = GenClass(
                    server_id=self.server_id,
                    host=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    private_key=self.private_key,
                )
                try:
                    gen.run(**effective_kwargs)
                except Exception as exc:
                    logger.error(
                        f"[srv={self.server_id}] {GenClass.__name__} failed: {exc}"
                    )
            cycle += 1

    def stop(self) -> None:
        self._stop_event.set()

class ScenarioScheduler:

    def __init__(self) -> None:
        self._runners: Dict[int, ServerScenarioRunner] = {}
        self._threads: Dict[int, threading.Thread] = {}

    def add_server(
        self,
        server_id: int,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        container_name: str = "test-app",
        rotation: str = "full",
    ) -> None:
        rotation_list = ROTATIONS.get(rotation, SCENARIO_ROTATION)
        runner = ServerScenarioRunner(
            server_id=server_id,
            host=host,
            port=port,
            username=username,
            password=password,
            private_key=private_key,
            container_name=container_name,
            rotation=rotation_list,
        )
        self._runners[server_id] = runner
        t = threading.Thread(
            target=runner.run,
            daemon=True,
            name=f"scenario-srv-{server_id}",
        )
        self._threads[server_id] = t
        t.start()
        logger.info(f"Scenario runner started for server_id={server_id}")

    def stop_all(self) -> None:
        for runner in self._runners.values():
            runner.stop()
        for t in self._threads.values():
            t.join(timeout=30)
