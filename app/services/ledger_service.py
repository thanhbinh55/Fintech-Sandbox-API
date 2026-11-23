"""Double-entry ledger service with atomic balance mutation."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InsufficientFundsException
from app.models import Account, LedgerEntry, Transaction


class LedgerService:
    @staticmethod
    def execute_transfer(
        db: Session,
        session_id: str,
        source_account_id: str,
        destination_account_id: str,
        amount_vnd: int,
        fee_vnd: int = 0,
        immediate_discount_vnd: int = 0,
        payment_intent_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Transaction:
        """Atomically debit source, credit destination, and record balanced double entries."""
        now = datetime.now(timezone.utc)

        # 1. Fetch and lock accounts
        source = db.execute(
            select(Account)
            .where(Account.id == source_account_id, Account.demo_session_id == session_id)
            .with_for_update()
        ).scalar_one_or_none()

        destination = db.execute(
            select(Account)
            .where(Account.id == destination_account_id, Account.demo_session_id == session_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not source or not destination:
            raise ValueError("Source or destination account not found in current session.")

        amount_debited = amount_vnd + fee_vnd - immediate_discount_vnd

        # Check funds/credit
        if source.available_balance_vnd < amount_debited:
            raise InsufficientFundsException(
                source_account_id=source.id,
                available_balance_vnd=source.available_balance_vnd,
                required_amount_vnd=amount_debited,
            )

        # 2. Update balances atomically
        source.available_balance_vnd -= amount_debited
        destination.available_balance_vnd += amount_vnd

        # 3. Create Transaction record
        tx = Transaction(
            demo_session_id=session_id,
            payment_intent_id=payment_intent_id,
            source_account_id=source.id,
            destination_account_id=destination.id,
            amount_vnd=amount_vnd,
            fee_vnd=fee_vnd,
            status="SUCCESS",
            idempotency_key=idempotency_key,
            created_at=now,
            completed_at=now,
        )
        db.add(tx)
        db.flush()

        # 4. Double-entry ledger records
        # Debit source for amount_debited
        debit_source_entry = LedgerEntry(
            transaction_id=tx.id,
            account_id=source.id,
            direction="DEBIT",
            amount_vnd=amount_debited,
            created_at=now,
        )
        # Credit destination for principal amount
        credit_dest_entry = LedgerEntry(
            transaction_id=tx.id,
            account_id=destination.id,
            direction="CREDIT",
            amount_vnd=amount_vnd,
            created_at=now,
        )
        db.add_all([debit_source_entry, credit_dest_entry])

        clearing_acc = db.execute(
            select(Account).where(
                Account.demo_session_id == session_id,
                Account.account_type == "INTERNAL_SETTLEMENT",
            )
        ).scalar_one_or_none()

        # If there's a fee, credit the internal settlement clearing account
        if fee_vnd > 0 and clearing_acc:
            clearing_acc.available_balance_vnd += fee_vnd
            fee_credit_entry = LedgerEntry(
                transaction_id=tx.id,
                account_id=clearing_acc.id,
                direction="CREDIT",
                amount_vnd=fee_vnd,
                created_at=now,
            )
            db.add(fee_credit_entry)

        # If there's an immediate discount, funded by clearing account
        if immediate_discount_vnd > 0 and clearing_acc:
            clearing_acc.available_balance_vnd -= immediate_discount_vnd
            discount_debit_entry = LedgerEntry(
                transaction_id=tx.id,
                account_id=clearing_acc.id,
                direction="DEBIT",
                amount_vnd=immediate_discount_vnd,
                created_at=now,
            )
            db.add(discount_debit_entry)

        db.flush()
        return tx
