"""Example B: Smart Routing workflow using Fintech Sandbox Client."""
import asyncio
from sdk.python.fintech_sandbox_client import FintechSandboxClient


async def run_smart_routing_example():
    base_url = "http://localhost:8000/v1"
    agent_token = "REPLACE_WITH_AGENT_TOKEN"
    client = FintechSandboxClient(base_url=base_url, token=agent_token)

    print("Step 1: Check available liquidity and payment sources...")
    sources = await client.get_payment_sources()
    for s in sources:
        print(f" - {s.display_name} ({s.account_type}): {s.available_funds_vnd:,} VND")

    print("\nStep 2: User asks 'Thanh toán 200.000đ nguồn nào hời nhất?'")
    # Resolve recipient (e.g. merchant or friend)
    contact = (await client.find_contacts("Lan")).matches[0]

    # Create draft
    draft = await client.create_payment_draft(
        recipient_id=contact.recipient_account_id,
        amount_vnd=200000,
        note="Thử nghiệm smart routing",
    )

    print("\nStep 3: Calculating deterministic quotes with backend optimization...")
    quotes = await client.get_payment_quotes(draft.id)

    recommended = next((q for q in quotes if q.recommended), None)
    if recommended:
        print(f"\n=> Khuyên dùng nguồn: {recommended.source_display_name}")
        print(f"   Chi phí hiệu quả: {recommended.effective_cost_vnd:,} VND")
        print(f"   Số tiền bị trừ ngay: {recommended.amount_debited_vnd:,} VND")
        print(f"   Hoàn tiền dự kiến: {recommended.estimated_reward_vnd:,} VND")
        print(f"   Ưu đãi áp dụng: {', '.join(recommended.applied_offer_names) or 'Không có'}")
        print(f"   Lý do: {recommended.eligibility_reason}")


if __name__ == "__main__":
    asyncio.run(run_smart_routing_example())

