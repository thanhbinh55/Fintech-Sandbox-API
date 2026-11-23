"""Payment Intent lifecycle, approval snapshot, and execution service."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Dict, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    CrossSessionAccessException,
    DuplicateRequestConflictException,
    InsufficientFundsException,
    InvalidStateTransitionException,
    QuoteExpiredException,
    ResourceNotFoundException,
)
from app.core.utils import ensure_utc
from app.models import (
    Account,
    IdempotencyRecord,
    PaymentApproval,
    PaymentIntent,
    PaymentQuote,
    Transaction,
)
from app.schemas.payment import (
    PaymentApprovalResponse,
    PaymentExecuteResponse,
    PaymentIntentCreate,
    PaymentIntentResponse,
    PaymentQuoteResponse,
)
from app.schemas.routing import RoutingCalculationResponse
from app.services.audit_service import AuditService
from app.services.ledger_service import LedgerService
from app.services.routing_service import RoutingService


class PaymentService:
    @staticmethod
    def create_intent(
        db: Session,
        session_id: str,
        user_id: str,
        req: PaymentIntentCreate,
        actor_type: str = "USER",
    ) -> PaymentIntentResponse:
        # Validate recipient account exists in the same session
        recipient = db.execute(
            select(Account).where(
                Account.id == req.recipient_account_id,
                Account.demo_session_id == session_id,
            )
        ).scalar_one_or_none()

        if not recipient:
            raise ResourceNotFoundException("RecipientAccount", req.recipient_account_id)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=2)

        intent = PaymentIntent(
            id=str(uuid.uuid4()),
            demo_session_id=session_id,
            creator_user_id=user_id,
            recipient_account_id=recipient.id,
            amount_vnd=req.amount_vnd,
            currency="VND",
            description=req.description,
            merchant_id=req.merchant_id,
            status="DRAFT",
            version=1,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        db.add(intent)
        db.flush()

        AuditService.record_event(
            db=db,
            session_id=session_id,
            actor_type=actor_type,
            actor_id=user_id,
            event_type="PAYMENT_INTENT_CREATED",
            entity_type="PAYMENT_INTENT",
            entity_id=intent.id,
            metadata={
                "amount_vnd": intent.amount_vnd,
                "recipient_account_id": intent.recipient_account_id,
                "description": intent.description,
            },
        )
        db.commit()
        db.refresh(intent)

        return PaymentService._build_intent_response(db, intent)

    @staticmethod
    def get_intent_by_id(
        db: Session, session_id: str, intent_id: str
    ) -> PaymentIntentResponse:
        intent = db.execute(
            select(PaymentIntent).where(
                PaymentIntent.id == intent_id,
                PaymentIntent.demo_session_id == session_id,
            )
        ).scalar_one_or_none()

        if not intent:
            raise ResourceNotFoundException("PaymentIntent", intent_id)

        return PaymentService._build_intent_response(db, intent)

    @staticmethod
    def generate_quotes(
        db: Session, session_id: str, user_id: str, intent_id: str, actor_type: str = "USER"
    ) -> RoutingCalculationResponse:
        intent = db.execute(
            select(PaymentIntent).where(
                PaymentIntent.id == intent_id,
                PaymentIntent.demo_session_id == session_id,
            )
        ).scalar_one_or_none()

        if not intent:
            raise ResourceNotFoundException("PaymentIntent", intent_id)

        if intent.status not in ["DRAFT", "QUOTED"]:
            raise InvalidStateTransitionException(intent.status, "generate_quotes")

        # Invalidate old active quotes
        for q in intent.quotes:
            if q.status == "ACTIVE":
                q.status = "EXPIRED"

        # Calculate new quotes
        calc_result = RoutingService.calculate_quotes(db, session_id, intent)
        intent.status = "QUOTED"
        intent.updated_at = datetime.now(timezone.utc)

        AuditService.record_event(
            db=db,
            session_id=session_id,
            actor_type=actor_type,
            actor_id=user_id,
            event_type="PAYMENT_QUOTES_GENERATED",
            entity_type="PAYMENT_INTENT",
            entity_id=intent.id,
            metadata={"quote_count": len(calc_result.quotes), "recommended_quote_id": calc_result.recommended_quote_id},
        )
        db.commit()
        return calc_result

    @staticmethod
    def approve_quote(
        db: Session, session_id: str, user_id: str, intent_id: str, quote_id: str
    ) -> PaymentApprovalResponse:
        """Approve a quote. Creates an immutable snapshot of payment parameters.

        Human-in-the-loop only.
        """
        intent = db.execute(
            select(PaymentIntent).where(
                PaymentIntent.id == intent_id,
                PaymentIntent.demo_session_id == session_id,
            )
        ).scalar_one_or_none()

        if not intent:
            raise ResourceNotFoundException("PaymentIntent", intent_id)

        if intent.status not in ["QUOTED", "AWAITING_APPROVAL", "DRAFT"]:
            raise InvalidStateTransitionException(intent.status, "approve")

        quote = db.execute(
            select(PaymentQuote).where(
                PaymentQuote.id == quote_id,
                PaymentQuote.payment_intent_id == intent.id,
            )
        ).scalar_one_or_none()

        if not quote:
            raise ResourceNotFoundException("PaymentQuote", quote_id)

        now = datetime.now(timezone.utc)
        if now > ensure_utc(quote.expires_at) or quote.status != "ACTIVE":
            raise QuoteExpiredException(quote.id)

        if not quote.eligible:
            raise InsufficientFundsException(
                source_account_id=quote.source_account_id,
                available_balance_vnd=quote.source_account.available_balance_vnd if quote.source_account else 0,
                required_amount_vnd=quote.amount_debited_vnd,
            )

        # Snapshot parameters immutably
        snapshot = {
            "intent_id": intent.id,
            "intent_version": intent.version,
            "quote_id": quote.id,
            "amount_vnd": quote.amount_vnd,
            "fee_vnd": quote.fee_vnd,
            "immediate_discount_vnd": quote.immediate_discount_vnd,
            "amount_debited_vnd": quote.amount_debited_vnd,
            "estimated_reward_vnd": quote.estimated_reward_vnd,
            "effective_cost_vnd": quote.effective_cost_vnd,
            "source_account_id": quote.source_account_id,
            "recipient_account_id": intent.recipient_account_id,
            "approved_at_iso": now.isoformat(),
        }

        # If approval exists, update it, otherwise create new
        approval = intent.approval
        if not approval:
            approval = PaymentApproval(
                payment_intent_id=intent.id,
                approved_quote_id=quote.id,
                actor_user_id=user_id,
                approved_intent_version=intent.version,
                approved_payment_snapshot=snapshot,
                approved_at=now,
            )
            db.add(approval)
        else:
            approval.approved_quote_id = quote.id
            approval.actor_user_id = user_id
            approval.approved_intent_version = intent.version
            approval.approved_payment_snapshot = snapshot
            approval.approved_at = now

        intent.status = "APPROVED"
        intent.updated_at = now

        AuditService.record_event(
            db=db,
            session_id=session_id,
            actor_type="USER",
            actor_id=user_id,
            event_type="PAYMENT_QUOTE_APPROVED",
            entity_type="PAYMENT_INTENT",
            entity_id=intent.id,
            metadata={"quote_id": quote.id, "amount_debited_vnd": quote.amount_debited_vnd},
        )
        db.commit()
        db.refresh(approval)

        return PaymentApprovalResponse(
            id=approval.id,
            payment_intent_id=approval.payment_intent_id,
            approved_quote_id=approval.approved_quote_id,
            actor_user_id=approval.actor_user_id,
            approved_intent_version=approval.approved_intent_version,
            approved_payment_snapshot=approval.approved_payment_snapshot,
            approved_at=approval.approved_at,
        )

    @staticmethod
    def execute_payment(
        db: Session,
        session_id: str,
        user_id: str,
        intent_id: str,
        idempotency_key: Optional[str] = None,
    ) -> PaymentExecuteResponse:
        """Atomically execute transfer based strictly on approved snapshot.

        Enforces idempotency, quote freshness, version matching, and ledger balance.
        """
        now = datetime.now(timezone.utc)

        # 1. Check idempotency record if key provided
        if idempotency_key:
            rec = db.execute(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.demo_session_id == session_id,
                    IdempotencyRecord.idempotency_key == idempotency_key,
                )
            ).scalar_one_or_none()

            if rec:
                # If key already exists, return cached payload
                cached = rec.response_payload
                return PaymentExecuteResponse(**cached)

        # 2. Fetch Intent
        intent = db.execute(
            select(PaymentIntent).where(
                PaymentIntent.id == intent_id,
                PaymentIntent.demo_session_id == session_id,
            )
        ).scalar_one_or_none()

        if not intent:
            raise ResourceNotFoundException("PaymentIntent", intent_id)

        # If already succeeded
        if intent.status == "SIMULATED_SUCCESS":
            tx = db.execute(
                select(Transaction).where(Transaction.payment_intent_id == intent.id)
            ).scalar_one_or_none()
            if tx:
                return PaymentExecuteResponse(
                    payment_intent_id=intent.id,
                    transaction_id=tx.id,
                    status="SIMULATED_SUCCESS",
                    amount_transferred_vnd=tx.amount_vnd,
                    fee_vnd=tx.fee_vnd,
                    amount_debited_vnd=tx.amount_vnd + tx.fee_vnd,
                    source_account_id=tx.source_account_id,
                    recipient_account_id=tx.destination_account_id,
                    completed_at=tx.completed_at or now,
                    message="Simulated transfer previously completed.",
                )

        if intent.status != "APPROVED":
            raise InvalidStateTransitionException(intent.status, "execute")

        approval = intent.approval
        if not approval:
            raise InvalidStateTransitionException("NO_APPROVAL", "execute")

        if approval.approved_intent_version != intent.version:
            raise InvalidStateTransitionException("APPROVAL_VERSION_MISMATCH", "execute")

        snapshot = approval.approved_payment_snapshot
        quote_id = approval.approved_quote_id

        quote = db.get(PaymentQuote, quote_id)
        if not quote:
            raise ResourceNotFoundException("PaymentQuote", quote_id)

        if now > ensure_utc(quote.expires_at):
            intent.status = "EXPIRED"
            db.commit()
            raise QuoteExpiredException(quote_id)

        # 3. Transition to PROCESSING
        intent.status = "PROCESSING"
        intent.updated_at = now
        db.flush()

        source_acc_id = snapshot["source_account_id"]
        dest_acc_id = snapshot["recipient_account_id"]
        amount_to_transfer = snapshot["amount_vnd"]
        fee_to_charge = snapshot["fee_vnd"]
        discount_given = snapshot.get("immediate_discount_vnd", 0)
        amount_to_debit = snapshot["amount_debited_vnd"]

        # 4. Atomic ledger mutation
        try:
            tx = LedgerService.execute_transfer(
                db=db,
                session_id=session_id,
                source_account_id=source_acc_id,
                destination_account_id=dest_acc_id,
                amount_vnd=amount_to_transfer,
                fee_vnd=fee_to_charge,
                immediate_discount_vnd=discount_given,
                payment_intent_id=intent.id,
                idempotency_key=idempotency_key,
            )

            intent.status = "SIMULATED_SUCCESS"
            intent.updated_at = now
            quote.status = "USED"

            AuditService.record_event(
                db=db,
                session_id=session_id,
                actor_type="USER",
                actor_id=user_id,
                event_type="PAYMENT_SIMULATED_SUCCESS",
                entity_type="PAYMENT_INTENT",
                entity_id=intent.id,
                metadata={
                    "transaction_id": tx.id,
                    "amount_vnd": amount_to_transfer,
                    "fee_vnd": fee_to_charge,
                    "source_id": source_acc_id,
                },
            )

            res = PaymentExecuteResponse(
                payment_intent_id=intent.id,
                transaction_id=tx.id,
                status="SIMULATED_SUCCESS",
                amount_transferred_vnd=amount_to_transfer,
                fee_vnd=fee_to_charge,
                amount_debited_vnd=amount_to_debit,
                source_account_id=source_acc_id,
                recipient_account_id=dest_acc_id,
                completed_at=now,
                message="Simulated transfer executed successfully in sandbox.",
            )

            # Store idempotency record if key provided
            if idempotency_key:
                req_hash = hashlib.sha256(f"{intent_id}:{user_id}".encode()).hexdigest()
                idem_rec = IdempotencyRecord(
                    demo_session_id=session_id,
                    scope_key="payment_execute",
                    idempotency_key=idempotency_key,
                    request_hash=req_hash,
                    status_code=200,
                    response_payload=res.model_dump(mode="json"),
                    created_at=now,
                    expires_at=now + timedelta(hours=24),
                )
                db.add(idem_rec)

            db.commit()
            return res

        except InsufficientFundsException:
            intent.status = "FAILED"
            intent.updated_at = now
            db.commit()
            raise

        except Exception as e:
            intent.status = "FAILED"
            intent.updated_at = now
            db.commit()
            raise

    @staticmethod
    def _build_intent_response(db: Session, intent: PaymentIntent) -> PaymentIntentResponse:
        quotes_res = []
        for q in intent.quotes:
            if q.status == "ACTIVE":
                quotes_res.append(
                    PaymentQuoteResponse(
                        id=q.id,
                        payment_intent_id=q.payment_intent_id,
                        source_account_id=q.source_account_id,
                        source_display_name=q.source_account.display_name if q.source_account else "",
                        source_type=q.source_account.account_type if q.source_account else "",
                        amount_vnd=q.amount_vnd,
                        fee_vnd=q.fee_vnd,
                        immediate_discount_vnd=q.immediate_discount_vnd,
                        amount_debited_vnd=q.amount_debited_vnd,
                        estimated_reward_vnd=q.estimated_reward_vnd,
                        effective_cost_vnd=q.effective_cost_vnd,
                        eligible=q.eligible,
                        eligibility_reason=q.eligibility_reason,
                        applied_offer_ids=q.applied_offer_ids or [],
                        applied_offer_names=[],
                        expires_at=q.expires_at,
                        recommended=False,
                    )
                )

        approval_res = None
        if intent.approval:
            app = intent.approval
            approval_res = PaymentApprovalResponse(
                id=app.id,
                payment_intent_id=app.payment_intent_id,
                approved_quote_id=app.approved_quote_id,
                actor_user_id=app.actor_user_id,
                approved_intent_version=app.approved_intent_version,
                approved_payment_snapshot=app.approved_payment_snapshot,
                approved_at=app.approved_at,
            )

        return PaymentIntentResponse(
            id=intent.id,
            creator_user_id=intent.creator_user_id,
            recipient_account_id=intent.recipient_account_id,
            recipient_display_name=intent.recipient_account.display_name if intent.recipient_account else None,
            amount_vnd=intent.amount_vnd,
            currency=intent.currency,
            description=intent.description,
            merchant_id=intent.merchant_id,
            status=intent.status,
            version=intent.version,
            created_at=intent.created_at,
            updated_at=intent.updated_at,
            expires_at=intent.expires_at,
            approval=approval_res,
            quotes=quotes_res,
        )
