"""Exact integer VND Bill Splitting and Settlement Service."""
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.models import (
    Account,
    SplitAssignment,
    SplitBill,
    SplitCollectionRequest,
    SplitItem,
    SplitParticipant,
)
from app.providers import ProviderQRRequest, get_qr_provider
from app.schemas.split import (
    SplitBillCreate,
    SplitBillResponse,
    SplitCollectionRequestResponse,
    SplitParticipantShareResponse,
    SplitStatusResponse,
)
from app.services.audit_service import AuditService
from app.services.ledger_service import LedgerService


class SplitService:
    @staticmethod
    def create_split_bill(
        db: Session,
        session_id: str,
        user_id: str,
        req: SplitBillCreate,
    ) -> SplitBillResponse:
        now = datetime.now(timezone.utc)

        # 1. Create SplitBill entity
        bill_id = str(uuid.uuid4())
        split_bill = SplitBill(
            id=bill_id,
            demo_session_id=session_id,
            creator_user_id=user_id,
            payer_participant_id="",  # will be assigned below
            title=req.title,
            total_amount_vnd=0,
            tax_vnd=req.tax_vnd,
            service_fee_vnd=req.service_fee_vnd,
            discount_vnd=req.discount_vnd,
            status="ACTIVE",
            created_at=now,
        )
        db.add(split_bill)
        db.flush()

        # 2. Register participants
        participant_map: Dict[str, SplitParticipant] = {}
        for p_input in req.participants:
            part = SplitParticipant(
                id=str(uuid.uuid4()),
                split_bill_id=bill_id,
                user_id=p_input.user_id,
                display_name=p_input.display_name.strip(),
                share_amount_vnd=0,
                paid_amount_vnd=0,
                status="PENDING",
            )
            db.add(part)
            db.flush()
            participant_map[part.display_name.lower()] = part

        # Determine payer participant
        payer_key = req.payer_name.strip().lower()
        if payer_key in participant_map:
            split_bill.payer_participant_id = participant_map[payer_key].id
        else:
            # If payer is not among participants, default to first participant
            split_bill.payer_participant_id = list(participant_map.values())[0].id

        # 3. Add items and assignments
        items_subtotal_vnd = 0
        participant_item_subtotals: Dict[str, int] = {p.id: 0 for p in participant_map.values()}

        for item_in in req.items:
            item_total = item_in.unit_price_vnd * item_in.quantity
            items_subtotal_vnd += item_total

            item = SplitItem(
                id=str(uuid.uuid4()),
                split_bill_id=bill_id,
                name=item_in.name,
                unit_price_vnd=item_in.unit_price_vnd,
                quantity=item_in.quantity,
                total_price_vnd=item_total,
            )
            db.add(item)
            db.flush()

            # Target participants for this item
            assigned_parts = []
            if item_in.assigned_participant_names:
                for name in item_in.assigned_participant_names:
                    k = name.strip().lower()
                    if k in participant_map:
                        assigned_parts.append(participant_map[k])
            # If none specified, item is shared by ALL participants
            if not assigned_parts:
                assigned_parts = list(participant_map.values())

            # Distribute item_total among assigned participants with exact integer division
            n_assigned = len(assigned_parts)
            base_share = item_total // n_assigned
            remainder = item_total % n_assigned

            # Deterministic remainder distribution: sorted by participant id
            sorted_assigned = sorted(assigned_parts, key=lambda p: p.id)
            for idx, p in enumerate(sorted_assigned):
                share = base_share + (1 if idx < remainder else 0)
                participant_item_subtotals[p.id] += share

                assignment = SplitAssignment(
                    id=str(uuid.uuid4()),
                    split_item_id=item.id,
                    participant_id=p.id,
                    weight=1,
                )
                db.add(assignment)

        # 4. Proportional distribution of Tax, Service Fee, and Discount
        total_bill_amount = items_subtotal_vnd + req.tax_vnd + req.service_fee_vnd - req.discount_vnd
        split_bill.total_amount_vnd = max(0, total_bill_amount)

        # Distribute adjustments
        participants_list = list(participant_map.values())
        participants_list.sort(key=lambda p: p.id)

        def distribute_proportional(total_pool: int) -> Dict[str, int]:
            if total_pool == 0 or items_subtotal_vnd == 0:
                return {p.id: 0 for p in participants_list}
            shares = {}
            allocated = 0
            for p in participants_list:
                part_sub = participant_item_subtotals[p.id]
                amt = (total_pool * part_sub) // items_subtotal_vnd
                shares[p.id] = amt
                allocated += amt
            # Remainder distribution
            rem = total_pool - allocated
            for idx in range(rem):
                shares[participants_list[idx % len(participants_list)].id] += 1
            return shares

        tax_shares = distribute_proportional(req.tax_vnd)
        fee_shares = distribute_proportional(req.service_fee_vnd)
        disc_shares = distribute_proportional(req.discount_vnd)

        # Compute final share per participant
        # Enforce sum(shares) == total_bill_amount
        allocated_total = 0
        for p in participants_list:
            share = (
                participant_item_subtotals[p.id]
                + tax_shares[p.id]
                + fee_shares[p.id]
                - disc_shares[p.id]
            )
            share = max(0, share)
            p.share_amount_vnd = share
            allocated_total += share

        # Check and resolve any round-off discrepancies
        discrepancy = split_bill.total_amount_vnd - allocated_total
        if discrepancy != 0:
            for idx in range(abs(discrepancy)):
                target_p = participants_list[idx % len(participants_list)]
                if discrepancy > 0:
                    target_p.share_amount_vnd += 1
                else:
                    if target_p.share_amount_vnd > 0:
                        target_p.share_amount_vnd -= 1

        # The payer participant's share is considered self-paid
        for p in participants_list:
            if p.id == split_bill.payer_participant_id:
                p.paid_amount_vnd = p.share_amount_vnd
                p.status = "SETTLED"
            else:
                p.paid_amount_vnd = 0
                p.status = "PENDING"

        # 5. Generate Collection Requests for participants who owe money
        qr_provider = get_qr_provider()
        for p in participants_list:
            if p.id != split_bill.payer_participant_id and p.share_amount_vnd > 0:
                req_id = str(uuid.uuid4())
                payer_part = next(pt for pt in participants_list if pt.id == split_bill.payer_participant_id)

                qr_req = ProviderQRRequest(
                    split_bill_id=bill_id,
                    collection_request_id=req_id,
                    participant_name=p.display_name,
                    requested_amount_vnd=p.share_amount_vnd,
                    recipient_name=payer_part.display_name,
                    description=f"Share of {split_bill.title}",
                )
                qr_res = qr_provider.generate_collection_qr(qr_req)

                col_req = SplitCollectionRequest(
                    id=req_id,
                    split_bill_id=bill_id,
                    participant_id=p.id,
                    requested_amount_vnd=p.share_amount_vnd,
                    collected_amount_vnd=0,
                    status="UNPAID",
                    qr_payload=qr_res.qr_payload,
                    payment_link=qr_res.payment_link,
                    created_at=now,
                    updated_at=now,
                )
                db.add(col_req)

        # Audit event
        AuditService.record_event(
            db=db,
            session_id=session_id,
            actor_type="USER",
            actor_id=user_id,
            event_type="SPLIT_BILL_CREATED",
            entity_type="SPLIT_BILL",
            entity_id=bill_id,
            metadata={"title": req.title, "total_amount_vnd": split_bill.total_amount_vnd},
        )
        db.commit()
        db.refresh(split_bill)

        return SplitService._build_split_response(db, split_bill)

    @staticmethod
    def get_split_bill(db: Session, session_id: str, split_id: str) -> SplitBillResponse:
        bill = db.execute(
            select(SplitBill).where(
                SplitBill.id == split_id,
                SplitBill.demo_session_id == session_id,
            )
        ).scalar_one_or_none()

        if not bill:
            raise ResourceNotFoundException("SplitBill", split_id)

        return SplitService._build_split_response(db, bill)

    @staticmethod
    def get_split_status(db: Session, session_id: str, split_id: str) -> SplitStatusResponse:
        bill = db.execute(
            select(SplitBill).where(
                SplitBill.id == split_id,
                SplitBill.demo_session_id == session_id,
            )
        ).scalar_one_or_none()

        if not bill:
            raise ResourceNotFoundException("SplitBill", split_id)

        total_collected = sum(p.paid_amount_vnd for p in bill.participants)
        remaining = max(0, bill.total_amount_vnd - total_collected)
        is_settled = remaining == 0

        participant_statuses = [
            SplitParticipantShareResponse(
                participant_id=p.id,
                display_name=p.display_name,
                is_payer=(p.id == bill.payer_participant_id),
                subtotal_items_vnd=p.share_amount_vnd,
                allocated_tax_vnd=0,
                allocated_fee_vnd=0,
                allocated_discount_vnd=0,
                total_share_vnd=p.share_amount_vnd,
                amount_paid_vnd=p.paid_amount_vnd,
                remaining_balance_vnd=max(0, p.share_amount_vnd - p.paid_amount_vnd),
                status=p.status,
            )
            for p in bill.participants
        ]

        return SplitStatusResponse(
            split_bill_id=bill.id,
            total_bill_amount_vnd=bill.total_amount_vnd,
            total_collected_vnd=total_collected,
            remaining_to_collect_vnd=remaining,
            is_fully_settled=is_settled,
            participant_statuses=participant_statuses,
        )

    @staticmethod
    def settle_collection_request(
        db: Session,
        session_id: str,
        split_id: str,
        request_id: str,
        amount_collected_vnd: Optional[int] = None,
    ) -> SplitCollectionRequestResponse:
        col_req = db.execute(
            select(SplitCollectionRequest).where(
                SplitCollectionRequest.id == request_id,
                SplitCollectionRequest.split_bill_id == split_id,
            )
        ).scalar_one_or_none()

        if not col_req:
            raise ResourceNotFoundException("SplitCollectionRequest", request_id)

        bill = col_req.split_bill
        participant = col_req.participant

        amount_to_pay = (
            amount_collected_vnd
            if amount_collected_vnd is not None
            else col_req.requested_amount_vnd - col_req.collected_amount_vnd
        )

        col_req.collected_amount_vnd += amount_to_pay
        if col_req.collected_amount_vnd >= col_req.requested_amount_vnd:
            col_req.status = "PAID"

        participant.paid_amount_vnd += amount_to_pay
        if participant.paid_amount_vnd >= participant.share_amount_vnd:
            participant.status = "SETTLED"

        # Check if all participants are settled
        if all(p.status == "SETTLED" for p in bill.participants):
            bill.status = "SETTLED"

        now = datetime.now(timezone.utc)
        col_req.updated_at = now

        AuditService.record_event(
            db=db,
            session_id=session_id,
            actor_type="USER",
            actor_id="SIMULATED_COLLECTOR",
            event_type="SPLIT_SHARE_COLLECTED",
            entity_type="SPLIT_COLLECTION_REQUEST",
            entity_id=col_req.id,
            metadata={"amount_collected_vnd": amount_to_pay, "status": col_req.status},
        )
        db.commit()
        db.refresh(col_req)

        return SplitCollectionRequestResponse(
            request_id=col_req.id,
            participant_id=col_req.participant_id,
            participant_name=participant.display_name,
            requested_amount_vnd=col_req.requested_amount_vnd,
            collected_amount_vnd=col_req.collected_amount_vnd,
            status=col_req.status,
            sandbox_payment_link=col_req.payment_link,
            qr_payload=col_req.qr_payload,
            created_at=col_req.created_at,
        )

    @staticmethod
    def _build_split_response(db: Session, bill: SplitBill) -> SplitBillResponse:
        participant_shares = []
        for p in bill.participants:
            is_payer = p.id == bill.payer_participant_id
            participant_shares.append(
                SplitParticipantShareResponse(
                    participant_id=p.id,
                    display_name=p.display_name,
                    is_payer=is_payer,
                    subtotal_items_vnd=p.share_amount_vnd,
                    allocated_tax_vnd=0,
                    allocated_fee_vnd=0,
                    allocated_discount_vnd=0,
                    total_share_vnd=p.share_amount_vnd,
                    amount_paid_vnd=p.paid_amount_vnd,
                    remaining_balance_vnd=max(0, p.share_amount_vnd - p.paid_amount_vnd),
                    status=p.status,
                )
            )

        collection_requests = []
        for cr in bill.collection_requests:
            is_external = "img.vietqr.io" in cr.payment_link
            collection_requests.append(
                SplitCollectionRequestResponse(
                    request_id=cr.id,
                    participant_id=cr.participant_id,
                    participant_name=cr.participant.display_name if cr.participant else "",
                    requested_amount_vnd=cr.requested_amount_vnd,
                    collected_amount_vnd=cr.collected_amount_vnd,
                    status=cr.status,
                    sandbox_payment_link=cr.payment_link,
                    qr_payload=cr.qr_payload,
                    provider_name="vietqr" if is_external else "internal_sandbox",
                    is_external_payment_rail=is_external,
                    created_at=cr.created_at,
                )
            )

        return SplitBillResponse(
            id=bill.id,
            title=bill.title,
            creator_user_id=bill.creator_user_id,
            payer_participant_id=bill.payer_participant_id or "",
            total_bill_amount_vnd=bill.total_amount_vnd,
            tax_vnd=bill.tax_vnd,
            service_fee_vnd=bill.service_fee_vnd,
            discount_vnd=bill.discount_vnd,
            status=bill.status,
            participant_shares=participant_shares,
            collection_requests=collection_requests,
            created_at=bill.created_at,
        )
