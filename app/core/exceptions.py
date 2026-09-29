from typing import Any, Optional

from fastapi import status

class AppException(Exception):  # noqa: N818 — "Exception" suffix is intentional

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    default_message: str = "Internal server error"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.code
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    default_message = "Resource not found"

class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    default_message = "Resource conflict"

class ValidationError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "validation_error"
    default_message = "Validation failed"

class AuthenticationError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_failed"
    default_message = "Authentication failed"

class PermissionDeniedError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    default_message = "Permission denied"

class SSHConnectionError(AppException):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "ssh_connection_error"
    default_message = "SSH connection failed"

class SecretsError(AppException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "secrets_error"
    default_message = "Secrets manager error"

class IntegrationError(AppException):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "integration_error"
    default_message = "External integration error"
