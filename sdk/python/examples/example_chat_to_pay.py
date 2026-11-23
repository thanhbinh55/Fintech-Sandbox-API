"""Example A: Chat-to-Pay workflow using Fintech Sandbox Client."""
import asyncio
from sdk.python.fintech_sandbox_client import FintechSandboxClient


async def run_chat_to_pay_example():
    # In real integration, Developer B provides base_url and agent_token from demo session creation
    base_url = "http://localhost:8000/v1"
    agent_token = "REPLACE_WITH_AGENT_TOKEN"
    client = FintechSandboxClient(base_url=base_url, token=agent_token)

    print("Step 1: AI extracts query 'Chuyển cho Minh 150 nghìn' and searches contacts...")
    contacts_res = await client.find_contacts("Minh")

    if contacts_res.is_ambiguous:
        print(f"Ambiguity detected! {contacts_res.clarification_message}")
        print("Candidate recipients:")
        for c in contacts_res.matches:
            print(f" - {c.display_name} ({c.alias or c.phone_number}), ID: {c.recipient_account_id}")
        return

    # Once recipient is resolved (e.g. Lan)
    recipient = (await client.find_contacts("Lan")).matches[0]
    print(f"Resolved recipient: {recipient.display_name} ({recipient.recipient_account_id})")

    print("\nStep 2: AI creates payment draft (safe operation for LLM)...")
    draft = await client.create_payment_draft(
        recipient_id=recipient.recipient_account_id,
        amount_vnd=150000,
        note="Tiền ăn tối hôm qua",
    )
    print(f"Draft created with ID: {draft.id}, Status: {draft.status}")

    print("\nStep 3: AI fetches smart routing quotes...")
    quotes = await client.get_payment_quotes(draft.id)
    for q in quotes:
        rec_tag = " [RECOMMENDED]" if q.recommended else ""
        print(f" - {q.source_display_name}: Chi phí thực tế {q.effective_cost_vnd:,}đ (Phí: {q.fee_vnd:,}đ, Giảm: {q.immediate_discount_vnd:,}đ){rec_tag}")

    print("\nStep 4: AI presents summary to user. The user approves explicitly in the UI.")
    print("NOTE: Execution is triggered by the application frontend using the USER token, NOT by the AI agent.")


if __name__ == "__main__":
    asyncio.run(run_chat_to_pay_example())

