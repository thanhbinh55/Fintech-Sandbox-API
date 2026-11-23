"""Transactions and ledger entries endpoints."""
import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenPayload, require_agent_or_user_scope
from app.database.session import get_db
from app.models import Transaction
from app.schemas.transaction import LedgerEntryResponse, TransactionResponse

router = APIRouter(prefix="/transactions", tags=["Transactions & Ledger"])


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")


@router.get("", summary="Get paginated transaction history for caller's demo session")
def get_transactions(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payload: TokenPayload = Depends(require_agent_or_user_scope),
    db: Session = Depends(get_db),
):
    query = (
        select(Transaction)
        .where(Transaction.demo_session_id == payload.session_id)
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    txs = db.execute(query).scalars().all()

    results = []
    for tx in txs:
        ledger_entries = [
            LedgerEntryResponse(
                id=le.id,
                account_id=le.account_id,
                direction=le.direction,
                amount_vnd=le.amount_vnd,
                created_at=le.created_at,
            )
            for le in tx.ledger_entries
        ]
        results.append(
            TransactionResponse(
                id=tx.id,
                payment_intent_id=tx.payment_intent_id,
                source_account_id=tx.source_account_id,
                source_display_name=tx.source_account.display_name if tx.source_account else None,
                destination_account_id=tx.destination_account_id,
                destination_display_name=tx.destination_account.display_name if tx.destination_account else None,
                amount_vnd=tx.amount_vnd,
                fee_vnd=tx.fee_vnd,
                status=tx.status,
                idempotency_key=tx.idempotency_key,
                created_at=tx.created_at,
                completed_at=tx.completed_at,
                ledger_entries=ledger_entries,
            )
        )

    return {"success": True, "data": results, "request_id": _req_id(request)}
