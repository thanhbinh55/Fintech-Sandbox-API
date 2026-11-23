"""Example C: Bill Splitting workflow using Fintech Sandbox Client."""
import asyncio
from sdk.python.fintech_sandbox_client import FintechSandboxClient


async def run_bill_splitting_example():
    base_url = "http://localhost:8000/v1"
    agent_token = "REPLACE_WITH_AGENT_TOKEN"
    client = FintechSandboxClient(base_url=base_url, token=agent_token)

    print("Step 1: Submitting structured bill extracted by OCR/Gemini...")
    structured_bill = {
        "title": "Bữa trưa đồng nghiệp",
        "payer_name": "An",
        "participants": [
            {"display_name": "An"},
            {"display_name": "Bình"},
            {"display_name": "Cường"},
        ],
        "items": [
            {
                "name": "Cơm tấm sườn bì",
                "unit_price_vnd": 50000,
                "quantity": 3,
                "assigned_participant_names": ["An", "Bình", "Cường"],
            },
            {
                "name": "Nước cam ép (An uống)",
                "unit_price_vnd": 30000,
                "quantity": 1,
                "assigned_participant_names": ["An"],
            },
        ],
        "tax_vnd": 0,
        "service_fee_vnd": 0,
        "discount_vnd": 0,
    }

    split_bill = await client.create_split_bill(structured_bill)
    print(f"Bill created: ID {split_bill.id}, Total: {split_bill.total_bill_amount_vnd:,} VND")

    print("\nParticipant allocation:")
    for p in split_bill.participant_shares:
        is_payer_tag = " (Payer / Đã trả trước)" if p["is_payer"] else ""
        print(f" - {p['display_name']}: {p['total_share_vnd']:,} VND{is_payer_tag}")

    print("\nCollection requests generated for non-payers:")
    for cr in split_bill.collection_requests:
        print(f" - Cho {cr['participant_name']}: {cr['requested_amount_vnd']:,} VND")
        print(f"   Sandbox QR payload: {cr['qr_payload']}")
        print(f"   Payment link: {cr['sandbox_payment_link']}")


if __name__ == "__main__":
    asyncio.run(run_bill_splitting_example())

