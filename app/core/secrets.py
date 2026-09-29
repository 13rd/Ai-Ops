from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import SecretsError

logger = logging.getLogger(__name__)

_FERNET_PREFIX = "gAAAAA"

class SecretsManager(ABC):

    @abstractmethod
    def encrypt(self, plaintext: str) -> str: ...

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str: ...

    def is_encrypted(self, value: str) -> bool:
        return bool(value) and value.startswith(_FERNET_PREFIX)

    def encrypt_if_needed(self, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return value
        if self.is_encrypted(value):
            return value
        return self.encrypt(value)

    def decrypt_if_encrypted(self, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return value
        if not self.is_encrypted(value):
            return value
        return self.decrypt(value)

class FernetSecretsManager(SecretsManager):
    def __init__(self, key: str) -> None:
        if not key:
            raise SecretsError("SSH_ENCRYPTION_KEY is not configured")
        try:
            self._fernet = Fernet(self._normalize_key(key))
        except (ValueError, TypeError) as exc:
            raise SecretsError(f"Invalid Fernet key: {exc}") from exc

    @staticmethod
    def _normalize_key(key: str) -> bytes:

        raw = key.encode("utf-8") if isinstance(key, str) else key
        try:
            decoded = base64.urlsafe_b64decode(raw)
            if len(decoded) == 32:
                return raw
        except Exception:
            pass

        import hashlib

        digest = hashlib.sha256(raw).digest()
        return base64.urlsafe_b64encode(digest)

    def encrypt(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretsError("Failed to decrypt secret: invalid token or key") from exc

@lru_cache(maxsize=1)
def get_secrets_manager() -> SecretsManager:

    return FernetSecretsManager(settings.SSH_ENCRYPTION_KEY)
