"""Unit and integration tests for Payment Intent State Machine transitions."""
import pytest
from app.core.exceptions import InvalidStateTransitionException
from app.models import Account, PaymentIntent
from app.schemas.payment import PaymentIntentCreate
from app.services.payment_service import PaymentService


def test_payment_state_machine_execution_without_approval_rejected(db_session, demo_session):
    primary_acc = db_session.query(Account).filter_by(demo_session_id=demo_session.id, account_type="EWALLET").first()
    recipient_acc = db_session.query(Account).filter(
        Account.demo_session_id == demo_session.id,
        Account.owner_user_id != primary_acc.owner_user_id,
        Account.account_type == "EWALLET"
    ).first()

    req = PaymentIntentCreate(
        recipient_account_id=recipient_acc.id,
        amount_vnd=50000,
        description="Test state machine",
    )
    intent_res = PaymentService.create_intent(db_session, demo_session.id, primary_acc.owner_user_id, req)
    assert intent_res.status == "DRAFT"

    # Attempting to execute DRAFT directly without approval must raise InvalidStateTransitionException
    with pytest.raises(InvalidStateTransitionException) as exc_info:
        PaymentService.execute_payment(
            db_session,
            session_id=demo_session.id,
            user_id=primary_acc.owner_user_id,
            intent_id=intent_res.id,
        )
    assert exc_info.value.code == "INVALID_STATE"


def test_payment_state_machine_approval_and_execution_lifecycle(db_session, demo_session):
    primary_acc = db_session.query(Account).filter_by(demo_session_id=demo_session.id, account_type="EWALLET").first()
    recipient_acc = db_session.query(Account).filter(
        Account.demo_session_id == demo_session.id,
        Account.owner_user_id != primary_acc.owner_user_id,
        Account.account_type == "EWALLET"
    ).first()

    initial_sender_balance = primary_acc.available_balance_vnd
    initial_recipient_balance = recipient_acc.available_balance_vnd

    # 1. Create intent
    req = PaymentIntentCreate(
        recipient_account_id=recipient_acc.id,
        amount_vnd=50000,
        description="Life cycle test",
    )
    intent = PaymentService.create_intent(db_session, demo_session.id, primary_acc.owner_user_id, req)
    assert intent.status == "DRAFT"

    # 2. Generate quotes
    quoted_intent = PaymentService.generate_quotes(db_session, demo_session.id, primary_acc.owner_user_id, intent.id)
    intent_db = PaymentService.get_intent_by_id(db_session, demo_session.id, intent.id)
    assert intent_db.status == "QUOTED"
    wallet_quote = next(q for q in quoted_intent.quotes if q.source_type == "EWALLET")

    # 3. Approve quote
    approval = PaymentService.approve_quote(
        db_session, demo_session.id, primary_acc.owner_user_id, intent.id, wallet_quote.id
    )
    assert approval.approved_quote_id == wallet_quote.id

    intent_after_approval = PaymentService.get_intent_by_id(db_session, demo_session.id, intent.id)
    assert intent_after_approval.status == "APPROVED"

    # 4. Execute payment
    exec_res = PaymentService.execute_payment(
        db_session,
        session_id=demo_session.id,
        user_id=primary_acc.owner_user_id,
        intent_id=intent.id,
    )
    assert exec_res.status == "SIMULATED_SUCCESS"
    assert exec_res.amount_transferred_vnd == 50000

    # 5. Check balances
    db_session.refresh(primary_acc)
    db_session.refresh(recipient_acc)
    assert primary_acc.available_balance_vnd == initial_sender_balance - 50000
    assert recipient_acc.available_balance_vnd == initial_recipient_balance + 50000
