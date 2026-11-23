"""SDK custom exception classes."""
from typing import Any, Dict, Optional


class FintechSandboxError(Exception):
    """Base exception for all Fintech Sandbox API errors."""

    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None, status_code: int = 400):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code


class AuthenticationError(FintechSandboxError):
    pass


class PermissionDeniedError(FintechSandboxError):
    pass


class ResourceNotFoundError(FintechSandboxError):
    pass


class InsufficientFundsError(FintechSandboxError):
    pass


class AmbiguousRecipientError(FintechSandboxError):
    pass


class QuoteExpiredError(FintechSandboxError):
    pass
