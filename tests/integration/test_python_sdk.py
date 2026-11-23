"""Tests verifying the Agent-facing Python SDK client."""
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from sdk.python.fintech_sandbox_client import FintechSandboxClient
from sdk.python.fintech_sandbox_client.exceptions import PermissionDeniedError


@pytest.mark.asyncio
async def test_python_sdk_agent_capabilities(client, demo_session):
    agent_token = demo_session.credentials.agent_token

    # Use ASGITransport to test FintechSandboxClient against in-process FastAPI app
    transport = ASGITransport(app=app)
    client = FintechSandboxClient(base_url="http://testserver/v1", token=agent_token)

    # Monkeypatch client._request to use ASGI transport
    async def asgi_request(method, path, params=None, json_data=None, headers=None):
        url = f"{client.base_url}{path}"
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            res = await ac.request(method, url, params=params, json=json_data, headers=client._headers(headers))
            data = res.json()
            if not data.get("success", False) or res.status_code >= 400:
                client._handle_error(res.status_code, data)
            return data.get("data", {})

    client._request = asgi_request

    # 1. find_contacts with ambiguity
    contacts_res = await client.find_contacts("Minh")
    assert contacts_res.is_ambiguous is True
    assert len(contacts_res.matches) == 2

    # 2. find_contacts unique
    unique_res = await client.find_contacts("Lan")
    assert unique_res.is_ambiguous is False
    assert len(unique_res.matches) == 1
    recipient_acc_id = unique_res.matches[0].recipient_account_id

    # 3. get_payment_sources
    sources = await client.get_payment_sources()
    assert len(sources) >= 3

    # 4. create_payment_draft
    draft = await client.create_payment_draft(
        recipient_id=recipient_acc_id,
        amount_vnd=150000,
        note="SDK test payment",
    )
    assert draft.amount_vnd == 150000
    assert draft.status == "DRAFT"

    # 5. get_payment_quotes
    quotes = await client.get_payment_quotes(draft.id)
    assert len(quotes) >= 3
    assert any(q.recommended for q in quotes)

    # 6. create_split_bill
    split_bill = await client.create_split_bill({
        "title": "SDK Bill Test",
        "payer_name": "An",
        "participants": [{"display_name": "An"}, {"display_name": "Bình"}],
        "items": [{"name": "Món ăn", "unit_price_vnd": 100000, "quantity": 1}],
        "tax_vnd": 0,
        "service_fee_vnd": 0,
        "discount_vnd": 0,
    })
    assert split_bill.total_bill_amount_vnd == 100000

    # 7. Agent cannot execute payment -> PermissionDeniedError
    with pytest.raises(PermissionDeniedError):
        await client.execute_payment(draft.id)
