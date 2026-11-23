"""Deterministic data seeding for demo scenarios."""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models import (
    Account,
    Contact,
    DemoSession,
    Offer,
    User,
)


def seed_demo_data(db: Session, session: DemoSession, scenario: str = "scenario_a") -> User:
    """Seed isolated, reproducible demo financial data for a session."""
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=90)
    past = now - timedelta(days=30)

    # 1. Primary User: An
    primary_user = User(
        demo_session_id=session.id,
        display_name="An (User)",
        role="PRIMARY_USER",
        phone_number="0901234567",
    )
    db.add(primary_user)
    db.flush()

    # 2. Other Participants/Contacts Users
    user_nguyen_minh = User(
        demo_session_id=session.id,
        display_name="Nguyễn Minh",
        role="PARTICIPANT",
        phone_number="0912345678",
    )
    user_tran_minh = User(
        demo_session_id=session.id,
        display_name="Trần Minh",
        role="PARTICIPANT",
        phone_number="0923456789",
    )
    user_lan = User(
        demo_session_id=session.id,
        display_name="Lan",
        role="PARTICIPANT",
        phone_number="0934567890",
    )
    user_binh = User(
        demo_session_id=session.id,
        display_name="Bình",
        role="PARTICIPANT",
        phone_number="0945678901",
    )
    user_cuong = User(
        demo_session_id=session.id,
        display_name="Cường",
        role="PARTICIPANT",
        phone_number="0956789012",
    )
    db.add_all([user_nguyen_minh, user_tran_minh, user_lan, user_binh, user_cuong])
    db.flush()

    # 3. System Clearing / Settlement Account
    clearing_acc = Account(
        demo_session_id=session.id,
        owner_user_id=primary_user.id,
        account_type="INTERNAL_SETTLEMENT",
        display_name="Tài khoản thanh toán trung gian Sandbox",
        account_number="SYS_SETTLEMENT_001",
        currency="VND",
        available_balance_vnd=0,
        enabled=True,
    )
    db.add(clearing_acc)

    # 4. Accounts for Primary User (An)
    # E-wallet: 1,500,000 VND
    wallet_acc = Account(
        demo_session_id=session.id,
        owner_user_id=primary_user.id,
        account_type="EWALLET",
        display_name="Ví MoMo Sandbox",
        account_number="MM_0901234567",
        currency="VND",
        available_balance_vnd=1500000,
        enabled=True,
    )
    # Bank A (Vietcombank): 5,000,000 VND
    bank_a_acc = Account(
        demo_session_id=session.id,
        owner_user_id=primary_user.id,
        account_type="SIMULATED_BANK",
        display_name="Vietcombank (Demo Bank)",
        account_number="VCB_9988776655",
        currency="VND",
        available_balance_vnd=5000000,
        enabled=True,
    )
    # Card B (Techcombank Credit Card): 2,000,000 VND available credit
    card_b_acc = Account(
        demo_session_id=session.id,
        owner_user_id=primary_user.id,
        account_type="SIMULATED_CARD",
        display_name="Techcombank Visa (Demo Card)",
        account_number="401288******1234",
        currency="VND",
        available_balance_vnd=2000000,
        credit_limit_vnd=10000000,
        enabled=True,
    )
    db.add_all([wallet_acc, bank_a_acc, card_b_acc])
    db.flush()

    # 5. Accounts for Contacts (Recipient accounts)
    acc_nguyen_minh = Account(
        demo_session_id=session.id,
        owner_user_id=user_nguyen_minh.id,
        account_type="EWALLET",
        display_name="Ví MoMo của Nguyễn Minh",
        account_number="MM_0912345678",
        currency="VND",
        available_balance_vnd=500000,
        enabled=True,
    )
    acc_tran_minh = Account(
        demo_session_id=session.id,
        owner_user_id=user_tran_minh.id,
        account_type="SIMULATED_BANK",
        display_name="BIDV của Trần Minh",
        account_number="BIDV_1122334455",
        currency="VND",
        available_balance_vnd=300000,
        enabled=True,
    )
    acc_lan = Account(
        demo_session_id=session.id,
        owner_user_id=user_lan.id,
        account_type="EWALLET",
        display_name="Ví MoMo của Lan",
        account_number="MM_0934567890",
        currency="VND",
        available_balance_vnd=1000000,
        enabled=True,
    )
    db.add_all([acc_nguyen_minh, acc_tran_minh, acc_lan])
    db.flush()

    # 6. Contacts saved by Primary User (An)
    contact_1 = Contact(
        demo_session_id=session.id,
        owner_user_id=primary_user.id,
        display_name="Nguyễn Minh",
        alias="Minh Đồng Nghiệp",
        phone_number="0912345678",
        recipient_account_id=acc_nguyen_minh.id,
        bank_name="Ví MoMo Sandbox",
    )
    contact_2 = Contact(
        demo_session_id=session.id,
        owner_user_id=primary_user.id,
        display_name="Trần Minh",
        alias="Minh Cấp 3",
        phone_number="0923456789",
        recipient_account_id=acc_tran_minh.id,
        bank_name="BIDV Sandbox",
    )
    contact_3 = Contact(
        demo_session_id=session.id,
        owner_user_id=primary_user.id,
        display_name="Lan",
        alias="Lan Bạn Thân",
        phone_number="0934567890",
        recipient_account_id=acc_lan.id,
        bank_name="Ví MoMo Sandbox",
    )
    db.add_all([contact_1, contact_2, contact_3])

    # 7. Promotional Offers / Rewards (Fictional Demo Data)
    offer_bank_cashback = Offer(
        demo_session_id=session.id,
        display_name="Hoàn tiền 5.000đ khi chuyển tiền qua Vietcombank (Sandbox)",
        code="VCB_CASHBACK_5K",
        eligible_source_types=["SIMULATED_BANK"],
        eligible_merchant_ids=None,
        minimum_amount_vnd=100000,
        maximum_discount_vnd=5000,
        reward_type="CASHBACK",
        reward_value_flat_vnd=5000,
        starts_at=past,
        expires_at=future,
        usage_limit=100,
        active=True,
    )
    offer_card_discount = Offer(
        demo_session_id=session.id,
        display_name="Giảm 10% tối đa 20.000đ qua thẻ Techcombank (Sandbox)",
        code="TCB_DISCOUNT_10PCT",
        eligible_source_types=["SIMULATED_CARD"],
        eligible_merchant_ids=None,
        minimum_amount_vnd=50000,
        maximum_discount_vnd=20000,
        reward_type="INSTANT_DISCOUNT",
        reward_value_percent=10.0,
        starts_at=past,
        expires_at=future,
        usage_limit=100,
        active=True,
    )
    offer_expired = Offer(
        demo_session_id=session.id,
        display_name="Khuyến mãi đã hết hạn (Sandbox Test)",
        code="EXPIRED_OFFER_DEMO",
        eligible_source_types=["EWALLET", "SIMULATED_BANK", "SIMULATED_CARD"],
        eligible_merchant_ids=None,
        minimum_amount_vnd=10000,
        maximum_discount_vnd=50000,
        reward_type="INSTANT_DISCOUNT",
        reward_value_flat_vnd=10000,
        starts_at=past - timedelta(days=30),
        expires_at=past,  # Expired
        usage_limit=100,
        active=False,
    )
    db.add_all([offer_bank_cashback, offer_card_discount, offer_expired])
    db.flush()

    return primary_user

