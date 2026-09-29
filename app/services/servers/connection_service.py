import asyncio
import logging
from io import StringIO
from typing import Optional, Tuple

import paramiko

from app.core.config import settings
from app.core.exceptions import SSHConnectionError
from app.models.server import Server

logger = logging.getLogger(__name__)

ConnectionError = SSHConnectionError

class SSHConnectionService:

    @staticmethod
    async def test_connection(server: Server) -> Tuple[bool, str, Optional[str]]:

        if server.connection_type != "ssh":
            return (
                False,
                f"Unsupported connection type: {server.connection_type}",
                "unsupported_type",
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            SSHConnectionService._test_ssh_connection_sync,
            server,
        )

    @staticmethod
    def _build_connect_kwargs(server: Server) -> dict:
        password = server.get_decrypted_password()
        private_key_text = server.get_decrypted_private_key()

        connect_kwargs: dict = {
            "hostname": server.host,
            "port": server.port,
            "username": server.ssh_username,
            "timeout": settings.SSH_TIMEOUT,
            "look_for_keys": False,
            "allow_agent": False,
        }

        if password:
            connect_kwargs["password"] = password
        elif private_key_text:
            connect_kwargs["pkey"] = paramiko.RSAKey.from_private_key(StringIO(private_key_text))
        else:
            raise SSHConnectionError("No credentials provided", code="no_credentials")

        return connect_kwargs

    @staticmethod
    def _test_ssh_connection_sync(server: Server) -> Tuple[bool, str, Optional[str]]:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            connect_kwargs = SSHConnectionService._build_connect_kwargs(server)
            client.connect(**connect_kwargs)

            _, stdout, _ = client.exec_command("echo 'test'")
            output = stdout.read().decode().strip()
            if output != "test":
                return False, "Command execution test failed", "command_failed"

            return True, "Connection successful", None

        except SSHConnectionError as exc:
            return False, exc.message, exc.code
        except paramiko.AuthenticationException:
            return False, "Authentication failed", "auth_failed"
        except paramiko.SSHException as exc:
            return False, f"SSH error: {exc}", "ssh_error"
        except TimeoutError:
            return False, "Connection timeout", "timeout"
        except Exception as exc:
            logger.exception("Unexpected SSH test failure for %s", server.host)
            return False, f"Connection error: {exc}", "connection_error"
        finally:
            try:
                client.close()
            except Exception:
                pass

    @staticmethod
    async def get_ssh_client(server: Server) -> paramiko.SSHClient:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            SSHConnectionService._get_ssh_client_sync,
            server,
        )

    @staticmethod
    def _get_ssh_client_sync(server: Server) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            connect_kwargs = SSHConnectionService._build_connect_kwargs(server)
            client.connect(**connect_kwargs)
            return client
        except SSHConnectionError:
            raise
        except paramiko.AuthenticationException as exc:
            raise SSHConnectionError("Authentication failed", code="auth_failed") from exc
        except paramiko.SSHException as exc:
            raise SSHConnectionError(f"SSH error: {exc}", code="ssh_error") from exc
        except TimeoutError as exc:
            raise SSHConnectionError("Connection timeout", code="timeout") from exc
        except Exception as exc:
            raise SSHConnectionError(f"Connection error: {exc}", code="connection_error") from exc
