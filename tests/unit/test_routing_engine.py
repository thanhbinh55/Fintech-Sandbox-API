"""Unit tests for Smart Routing Engine calculations and ranking."""
import pytest
from datetime import datetime, timezone, timedelta
from app.models import Account, Offer, PaymentIntent
from app.services.routing_service import RoutingService


def test_routing_fee_and_ranking(db_session, demo_session):
    # Scenario A has 3 accounts for primary user:
    # 1. EWALLET (Ví MoMo): 1,500,000 VND (fee 0)
    # 2. SIMULATED_BANK (VCB): 5,000,000 VND (fee 0, cashback 5,000 VND when >= 100k)
    # 3. SIMULATED_CARD (TCB): 2,000,000 VND available (fee 1,000 VND, 10% discount max 20k when >= 50k)

    primary_acc = db_session.query(Account).filter_by(demo_session_id=demo_session.id, account_type="EWALLET").first()
    recipient_acc = db_session.query(Account).filter(
        Account.demo_session_id == demo_session.id,
        Account.owner_user_id != primary_acc.owner_user_id
    ).first()

    intent = PaymentIntent(
        id="test-intent-100k",
        demo_session_id=demo_session.id,
        creator_user_id=primary_acc.owner_user_id,
        recipient_account_id=recipient_acc.id,
        amount_vnd=150000,
        currency="VND",
        description="Thanh toan an toi",
        status="DRAFT",
        version=1,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(intent)
    db_session.commit()

    routing_res = RoutingService.calculate_quotes(db_session, demo_session.id, intent)

    assert len(routing_res.quotes) == 3
    quotes = routing_res.quotes

    # Check that Card has fee 1,000 VND and 10% discount capped at 20k (15,000 VND discount)
    card_quote = next(q for q in quotes if q.source_type == "SIMULATED_CARD")
    assert card_quote.fee_vnd == 1000
    assert card_quote.immediate_discount_vnd == 15000
    assert card_quote.amount_debited_vnd == 150000 + 1000 - 15000  # 136,000 VND
    assert card_quote.effective_cost_vnd == 136000

    # Check that Bank has 0 fee and 5,000 VND cashback
    bank_quote = next(q for q in quotes if q.source_type == "SIMULATED_BANK")
    assert bank_quote.fee_vnd == 0
    assert bank_quote.estimated_reward_vnd == 5000
    assert bank_quote.effective_cost_vnd == 145000

    # Check Wallet has 0 fee and 0 discount
    wallet_quote = next(q for q in quotes if q.source_type == "EWALLET")
    assert wallet_quote.fee_vnd == 0
    assert wallet_quote.immediate_discount_vnd == 0
    assert wallet_quote.effective_cost_vnd == 150000

    # Best quote should be Card (effective cost 136,000 VND)
    assert routing_res.recommended_quote_id == card_quote.id
    assert card_quote.recommended is True


def test_routing_insufficient_funds_handling(db_session, demo_session):
    # Payment amount exceeding wallet balance (e.g. 3,000,000 VND)
    # Wallet balance is 1,500,000 VND, so wallet must be marked eligible = False
    primary_acc = db_session.query(Account).filter_by(demo_session_id=demo_session.id, account_type="EWALLET").first()
    recipient_acc = db_session.query(Account).filter(
        Account.demo_session_id == demo_session.id,
        Account.owner_user_id != primary_acc.owner_user_id
    ).first()

    intent = PaymentIntent(
        id="test-intent-3m",
        demo_session_id=demo_session.id,
        creator_user_id=primary_acc.owner_user_id,
        recipient_account_id=recipient_acc.id,
        amount_vnd=3000000,
        currency="VND",
        description="Thanh toan lon",
        status="DRAFT",
        version=1,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(intent)
    db_session.commit()

    routing_res = RoutingService.calculate_quotes(db_session, demo_session.id, intent)
    wallet_quote = next(q for q in routing_res.quotes if q.source_type == "EWALLET")

    assert wallet_quote.eligible is False
    assert "INSUFFICIENT_FUNDS" in wallet_quote.explanation_codes
    # Bank has 5,000,000 VND so Bank must remain eligible
    bank_quote = next(q for q in routing_res.quotes if q.source_type == "SIMULATED_BANK")
    assert bank_quote.eligible is True
