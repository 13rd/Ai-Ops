import asyncio
import logging
from typing import Optional, Tuple

import paramiko

from app.core.config import settings
from app.models.server import Server

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Base exception for connection errors."""

    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class SSHConnectionService:
    """
    Service for SSH connection testing and management.
    Abstracted to allow easy replacement with other connection types.
    """

    @staticmethod
    async def test_connection(server: Server) -> Tuple[bool, str, Optional[str]]:
        """
        Test SSH connection to server.
        Returns: (success: bool, message: str, error_code: Optional[str])
        """
        if server.connection_type != "ssh":
            return (
                False,
                f"Unsupported connection type: {server.connection_type}",
                "UNSUPPORTED_TYPE",
            )

        try:
            # Run SSH connection in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                SSHConnectionService._test_ssh_connection_sync,
                server,
            )
            return result
        except Exception as e:
            logger.error(f"Unexpected error testing connection to {server.host}: {e}")
            return False, f"Unexpected error: {str(e)}", "UNEXPECTED_ERROR"

    @staticmethod
    def _test_ssh_connection_sync(server: Server) -> Tuple[bool, str, Optional[str]]:
        """
        Synchronous SSH connection test.
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Prepare connection parameters
            connect_kwargs = {
                "hostname": server.host,
                "port": server.port,
                "username": server.ssh_username,
                "timeout": settings.SSH_TIMEOUT,
            }

            # Use password or private key
            if server.ssh_password:
                # TODO: Decrypt password from vault
                connect_kwargs["password"] = server.ssh_password
            elif server.ssh_private_key:
                # TODO: Decrypt private key from vault
                from io import StringIO

                private_key = paramiko.RSAKey.from_private_key(StringIO(server.ssh_private_key))
                connect_kwargs["pkey"] = private_key
            else:
                return False, "No credentials provided", "NO_CREDENTIALS"

            # Attempt connection
            client.connect(**connect_kwargs)

            # Test command execution
            stdin, stdout, stderr = client.exec_command("echo 'test'")
            output = stdout.read().decode().strip()

            if output != "test":
                return False, "Command execution test failed", "COMMAND_FAILED"

            client.close()
            return True, "Connection successful", None

        except paramiko.AuthenticationException:
            return False, "Authentication failed", "AUTH_FAILED"
        except paramiko.SSHException as e:
            return False, f"SSH error: {str(e)}", "SSH_ERROR"
        except TimeoutError:
            return False, "Connection timeout", "TIMEOUT"
        except Exception as e:
            return False, f"Connection error: {str(e)}", "CONNECTION_ERROR"
        finally:
            try:
                client.close()
            except:
                pass

    @staticmethod
    async def get_ssh_client(server: Server) -> paramiko.SSHClient:
        """
        Get connected SSH client for server.
        Raises ConnectionError if connection fails.
        """
        loop = asyncio.get_event_loop()
        client = await loop.run_in_executor(
            None,
            SSHConnectionService._get_ssh_client_sync,
            server,
        )
        return client

    @staticmethod
    def _get_ssh_client_sync(server: Server) -> paramiko.SSHClient:
        """
        Synchronous SSH client creation.
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            connect_kwargs = {
                "hostname": server.host,
                "port": server.port,
                "username": server.ssh_username,
                "timeout": settings.SSH_TIMEOUT,
            }

            if server.ssh_password:
                connect_kwargs["password"] = server.ssh_password
            elif server.ssh_private_key:
                from io import StringIO

                private_key = paramiko.RSAKey.from_private_key(StringIO(server.ssh_private_key))
                connect_kwargs["pkey"] = private_key
            else:
                raise ConnectionError("No credentials provided", "NO_CREDENTIALS")

            client.connect(**connect_kwargs)
            return client

        except paramiko.AuthenticationException:
            raise ConnectionError("Authentication failed", "AUTH_FAILED")
        except paramiko.SSHException as e:
            raise ConnectionError(f"SSH error: {str(e)}", "SSH_ERROR")
        except TimeoutError:
            raise ConnectionError("Connection timeout", "TIMEOUT")
        except Exception as e:
            raise ConnectionError(f"Connection error: {str(e)}", "CONNECTION_ERROR")
