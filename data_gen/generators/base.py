import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

import paramiko

from app.models.anomaly_event import AnomalyEvent
from data_gen.db import SessionLocal

logger = logging.getLogger(__name__)

class BaseGenerator(ABC):

    scenario_type: str

    def __init__(
        self,
        server_id: int,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> None:
        self.server_id = server_id
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self._event_id: Optional[int] = None

    def _make_client(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: dict = {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "timeout": 10,
        }
        if self.password:
            kwargs["password"] = self.password
        elif self.private_key:
            from io import StringIO
            kwargs["pkey"] = paramiko.RSAKey.from_private_key(StringIO(self.private_key))
        client.connect(**kwargs)
        return client

    def _ssh(self, client: paramiko.SSHClient, command: str) -> str:
        _, stdout, _ = client.exec_command(command)
        return stdout.read().decode().strip()

    def _open_event(self, parameters: Dict[str, Any]) -> int:
        db = SessionLocal()
        try:
            event = AnomalyEvent(
                server_id=self.server_id,
                scenario_type=self.scenario_type,
                start_ts=datetime.utcnow(),
                end_ts=None,
                parameters=parameters,
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            self._event_id = event.id
            logger.info(f"Opened AnomalyEvent id={event.id} type={self.scenario_type} srv={self.server_id}")
            return event.id
        finally:
            db.close()

    def _close_event(self, extra_parameters: Dict[str, Any]) -> None:
        if self._event_id is None:
            return
        db = SessionLocal()
        try:
            event = db.get(AnomalyEvent, self._event_id)
            if event:
                event.end_ts = datetime.utcnow()
                event.parameters = {**event.parameters, **extra_parameters}
                db.commit()
                logger.info(f"Closed AnomalyEvent id={self._event_id}")
        finally:
            db.close()

    @abstractmethod
    def run(self, **kwargs: Any) -> None:
        pass
