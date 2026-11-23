"""Application custom exceptions and error models."""
from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class FintechSandboxException(Exception):
    """Base exception for all domain errors in Fintech Sandbox."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ResourceNotFoundException(FintechSandboxException):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource_type} with ID '{resource_id}' was not found in your demo session.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class UnauthorizedException(FintechSandboxException):
    def __init__(self, message: str = "Authentication token is missing or invalid."):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenException(FintechSandboxException):
    def __init__(self, message: str = "Access denied: insufficient permission scope."):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class InsufficientFundsException(FintechSandboxException):
    def __init__(
        self,
        source_account_id: str,
        available_balance_vnd: int,
        required_amount_vnd: int,
    ):
        super().__init__(
            code="INSUFFICIENT_FUNDS",
            message=f"Source account available balance ({available_balance_vnd} VND) is insufficient for debit ({required_amount_vnd} VND).",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                "source_account_id": source_account_id,
                "available_balance_vnd": available_balance_vnd,
                "required_amount_vnd": required_amount_vnd,
            },
        )


class AmbiguousRecipientException(FintechSandboxException):
    def __init__(self, query: str, matching_contacts: list):
        super().__init__(
            code="AMBIGUOUS_RECIPIENT",
            message=f"Multiple contacts matched search query '{query}'. Clarification needed.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"query": query, "matching_contacts": matching_contacts},
        )


class QuoteExpiredException(FintechSandboxException):
    def __init__(self, quote_id: str):
        super().__init__(
            code="QUOTE_EXPIRED",
            message=f"Payment quote '{quote_id}' has expired. Please recalculate quotes.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"quote_id": quote_id},
        )


class InvalidStateTransitionException(FintechSandboxException):
    def __init__(self, current_state: str, attempted_action: str):
        super().__init__(
            code="INVALID_STATE",
            message=f"Cannot perform '{attempted_action}' while payment intent is in state '{current_state}'.",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"current_state": current_state, "attempted_action": attempted_action},
        )


class DuplicateRequestConflictException(FintechSandboxException):
    def __init__(self, idempotency_key: str):
        super().__init__(
            code="DUPLICATE_REQUEST",
            message=f"Idempotency conflict: key '{idempotency_key}' was previously used with differing parameters.",
            status_code=status.HTTP_409_CONFLICT,
            details={"idempotency_key": idempotency_key},
        )


class CrossSessionAccessException(FintechSandboxException):
    def __init__(self):
        super().__init__(
            code="CROSS_SESSION_ACCESS_DENIED",
            message="Cross-session access detected and blocked. Resource belongs to another demo session.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
