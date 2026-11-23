"""Asynchronous HTTP Client for Fintech Sandbox API."""
from typing import Any, Dict, List, Optional
import httpx

from sdk.python.fintech_sandbox_client.exceptions import (
    AmbiguousRecipientError,
    AuthenticationError,
    FintechSandboxError,
    InsufficientFundsError,
    PermissionDeniedError,
    QuoteExpiredError,
    ResourceNotFoundError,
)
from sdk.python.fintech_sandbox_client.models import (
    Contact,
    ContactSearchResult,
    PaymentIntent,
    PaymentQuote,
    PaymentSource,
    SplitBill,
    SplitStatus,
)


class FintechSandboxClient:
    """Agent and Application Client for Fintech Sandbox API.

    Supports asynchronous operations, scoped tokens, structured exception mapping,
    and automatic envelope extraction.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        token: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _handle_error(self, status_code: int, response_json: Dict[str, Any]) -> None:
        err = response_json.get("error", {})
        code = err.get("code", "UNKNOWN_ERROR")
        message = err.get("message", "An error occurred in Fintech Sandbox API.")
        details = err.get("details", {})

        if code == "UNAUTHORIZED":
            raise AuthenticationError(code, message, details, status_code)
        if code in ("FORBIDDEN", "CROSS_SESSION_ACCESS_DENIED"):
            raise PermissionDeniedError(code, message, details, status_code)
        if code in ("RESOURCE_NOT_FOUND", "CONTACT_NOT_FOUND"):
            raise ResourceNotFoundError(code, message, details, status_code)
        if code == "INSUFFICIENT_FUNDS":
            raise InsufficientFundsError(code, message, details, status_code)
        if code == "AMBIGUOUS_RECIPIENT":
            raise AmbiguousRecipientError(code, message, details, status_code)
        if code == "QUOTE_EXPIRED":
            raise QuoteExpiredError(code, message, details, status_code)

        raise FintechSandboxError(code, message, details, status_code)

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json_data,
                headers=self._headers(headers),
            )
            try:
                res_json = response.json()
            except Exception:
                response.raise_for_status()
                return {}

            if not res_json.get("success", False) or response.status_code >= 400:
                self._handle_error(response.status_code, res_json)

            return res_json.get("data", {})

    # =========================================================================
    # AGENT TOOL-SAFE CAPABILITIES (Callable by LLM via AI Backend)
    # =========================================================================

    async def find_contacts(self, query: str) -> ContactSearchResult:
        """Search contacts by name, alias, or phone with ambiguity detection."""
        data = await self._request("GET", "/contacts", params={"q": query})
        return ContactSearchResult(**data)

    async def get_contact(self, contact_id: str) -> Contact:
        """Retrieve details of a single contact."""
        data = await self._request("GET", f"/contacts/{contact_id}")
        return Contact(**data)

    async def get_payment_sources(self) -> List[PaymentSource]:
        """List available payment sources and liquidity for the user."""
        data = await self._request("GET", "/payment-sources")
        return [PaymentSource(**item) for item in data]

    async def get_account_snapshot(self) -> List[Dict[str, Any]]:
        """Get snapshot of accounts and balances."""
        return await self._request("GET", "/me/accounts")

    async def create_payment_draft(
        self,
        recipient_id: str,
        amount_vnd: int,
        note: str,
        merchant_id: Optional[str] = None,
    ) -> PaymentIntent:
        """Create a payment intent draft. Safe for AI Agent initiation."""
        payload = {
            "recipient_account_id": recipient_id,
            "amount_vnd": amount_vnd,
            "description": note,
            "merchant_id": merchant_id,
        }
        data = await self._request("POST", "/payment-intents", json_data=payload)
        return PaymentIntent(**data)

    async def get_payment_quotes(self, payment_intent_id: str) -> List[PaymentQuote]:
        """Calculate and retrieve ranked payment quotes for an intent."""
        data = await self._request("POST", f"/payment-intents/{payment_intent_id}/quotes")
        return [PaymentQuote(**item) for item in data.get("quotes", [])]

    async def get_payment_intent(self, payment_intent_id: str) -> PaymentIntent:
        """Retrieve payment intent status and details."""
        data = await self._request("GET", f"/payment-intents/{payment_intent_id}")
        return PaymentIntent(**data)

    async def get_transaction_history(
        self, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve paginated transaction history."""
        return await self._request("GET", "/transactions", params={"limit": limit, "offset": offset})

    async def create_split_bill(self, structured_bill: Dict[str, Any]) -> SplitBill:
        """Create an itemized split bill with exact integer calculations."""
        data = await self._request("POST", "/split-bills", json_data=structured_bill)
        return SplitBill(**data)

    async def get_split_bill(self, split_id: str) -> SplitBill:
        """Retrieve a split bill by ID."""
        data = await self._request("GET", f"/split-bills/{split_id}")
        return SplitBill(**data)

    async def get_split_status(self, split_id: str) -> SplitStatus:
        """Retrieve settlement progress of a split bill."""
        data = await self._request("GET", f"/split-bills/{split_id}/status")
        return SplitStatus(**data)

    # =========================================================================
    # USER APPLICATION ACTIONS (Human-In-The-Loop Only - NOT for LLM registry)
    # =========================================================================

    async def approve_payment(self, payment_intent_id: str, quote_id: str) -> Dict[str, Any]:
        """Approve a quote. Requires user scope."""
        return await self._request(
            "POST",
            f"/payment-intents/{payment_intent_id}/approve",
            json_data={"quote_id": quote_id},
        )

    async def execute_payment(
        self,
        payment_intent_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a payment. Requires user scope."""
        payload = {"idempotency_key": idempotency_key} if idempotency_key else {}
        return await self._request(
            "POST",
            f"/payment-intents/{payment_intent_id}/execute",
            json_data=payload,
        )
