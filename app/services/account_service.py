"""Account and payment source query service."""
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.models import Account
from app.schemas.account import AccountResponse, PaymentSourceResponse


class AccountService:
    @staticmethod
    def get_user_accounts(db: Session, session_id: str, user_id: str) -> List[AccountResponse]:
        query = select(Account).where(
            Account.demo_session_id == session_id,
            Account.owner_user_id == user_id,
        ).order_by(Account.created_at.asc())
        accounts = db.execute(query).scalars().all()
        return [
            AccountResponse(
                id=acc.id,
                owner_user_id=acc.owner_user_id,
                account_type=acc.account_type,
                display_name=acc.display_name,
                account_number=acc.account_number,
                currency=acc.currency,
                available_balance_vnd=acc.available_balance_vnd,
                credit_limit_vnd=acc.credit_limit_vnd,
                enabled=acc.enabled,
                created_at=acc.created_at,
            )
            for acc in accounts
        ]

    @staticmethod
    def get_payment_sources(db: Session, session_id: str, user_id: str) -> List[PaymentSourceResponse]:
        query = select(Account).where(
            Account.demo_session_id == session_id,
            Account.owner_user_id == user_id,
            Account.account_type.in_(["EWALLET", "SIMULATED_BANK", "SIMULATED_CARD"]),
        ).order_by(Account.created_at.asc())
        accounts = db.execute(query).scalars().all()

        results = []
        for acc in accounts:
            is_credit = acc.account_type == "SIMULATED_CARD"
            # Mask account number
            raw_num = acc.account_number
            if len(raw_num) > 8:
                masked = f"{raw_num[:4]}****{raw_num[-4:]}"
            else:
                masked = raw_num

            # Icon hint
            icon_hint = "wallet" if acc.account_type == "EWALLET" else ("credit_card" if is_credit else "bank")

            results.append(
                PaymentSourceResponse(
                    source_id=acc.id,
                    account_type=acc.account_type,
                    display_name=acc.display_name,
                    account_number_masked=masked,
                    currency=acc.currency,
                    available_funds_vnd=acc.available_balance_vnd,
                    is_credit=is_credit,
                    credit_limit_vnd=acc.credit_limit_vnd,
                    enabled=acc.enabled,
                    icon_hint=icon_hint,
                )
            )
        return results

    @staticmethod
    def get_payment_source_by_id(db: Session, session_id: str, user_id: str, source_id: str) -> PaymentSourceResponse:
        acc = db.execute(
            select(Account).where(
                Account.id == source_id,
                Account.demo_session_id == session_id,
                Account.owner_user_id == user_id,
            )
        ).scalar_one_or_none()

        if not acc:
            raise ResourceNotFoundException("PaymentSource", source_id)

        is_credit = acc.account_type == "SIMULATED_CARD"
        raw_num = acc.account_number
        masked = f"{raw_num[:4]}****{raw_num[-4:]}" if len(raw_num) > 8 else raw_num
        icon_hint = "wallet" if acc.account_type == "EWALLET" else ("credit_card" if is_credit else "bank")

        return PaymentSourceResponse(
            source_id=acc.id,
            account_type=acc.account_type,
            display_name=acc.display_name,
            account_number_masked=masked,
            currency=acc.currency,
            available_funds_vnd=acc.available_balance_vnd,
            is_credit=is_credit,
            credit_limit_vnd=acc.credit_limit_vnd,
            enabled=acc.enabled,
            icon_hint=icon_hint,
        )

