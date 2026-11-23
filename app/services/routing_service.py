"""Deterministic Smart Payment Routing Engine."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Offer, PaymentIntent, PaymentQuote
from app.schemas.payment import PaymentQuoteResponse
from app.schemas.routing import RoutingCalculationResponse


class RoutingService:
    @staticmethod
    def calculate_quotes(
        db: Session,
        session_id: str,
        intent: PaymentIntent,
    ) -> RoutingCalculationResponse:
        """Evaluate all sources for an intent, calculate fees, discounts, and rewards,

        and rank them deterministically.
        """
        now = datetime.now(timezone.utc)
        quote_expiry = now + timedelta(minutes=15)

        # 1. Fetch user's candidate payment sources
        sources = db.execute(
            select(Account).where(
                Account.demo_session_id == session_id,
                Account.owner_user_id == intent.creator_user_id,
                Account.account_type.in_(["EWALLET", "SIMULATED_BANK", "SIMULATED_CARD"]),
            )
        ).scalars().all()

        # 2. Fetch active offers for session
        offers = db.execute(
            select(Offer).where(
                Offer.demo_session_id == session_id,
                Offer.active.is_(True),
                Offer.starts_at <= now,
                Offer.expires_at >= now,
            )
        ).scalars().all()

        quote_models: List[PaymentQuote] = []
        quote_responses: List[PaymentQuoteResponse] = []

        for source in sources:
            fee_vnd = 0
            if source.account_type == "SIMULATED_CARD":
                fee_vnd = 1000  # Standard flat sandbox processing fee for credit cards

            immediate_discount_vnd = 0
            estimated_reward_vnd = 0
            applied_offer_ids = []
            applied_offer_names = []
            explanation_codes = []

            # Check eligibility conditions
            eligible = True
            eligibility_reasons = []

            if not source.enabled:
                eligible = False
                eligibility_reasons.append("Tài khoản đang bị tạm khóa.")
                explanation_codes.append("SOURCE_DISABLED")

            # Match offers
            for offer in offers:
                if offer.eligible_source_types and source.account_type not in offer.eligible_source_types:
                    continue
                if offer.eligible_merchant_ids and intent.merchant_id not in offer.eligible_merchant_ids:
                    continue
                if intent.amount_vnd < offer.minimum_amount_vnd:
                    continue

                # Calculate benefit
                if offer.reward_type == "INSTANT_DISCOUNT":
                    disc = 0
                    if offer.reward_value_percent:
                        disc = int(intent.amount_vnd * (float(offer.reward_value_percent) / 100.0))
                    elif offer.reward_value_flat_vnd:
                        disc = offer.reward_value_flat_vnd

                    if offer.maximum_discount_vnd > 0:
                        disc = min(disc, offer.maximum_discount_vnd)

                    immediate_discount_vnd += disc
                    applied_offer_ids.append(offer.id)
                    applied_offer_names.append(offer.display_name)
                    explanation_codes.append("OFFER_APPLIED_DISCOUNT")

                elif offer.reward_type == "CASHBACK":
                    cashback = 0
                    if offer.reward_value_percent:
                        cashback = int(intent.amount_vnd * (float(offer.reward_value_percent) / 100.0))
                    elif offer.reward_value_flat_vnd:
                        cashback = offer.reward_value_flat_vnd

                    if offer.maximum_discount_vnd > 0:
                        cashback = min(cashback, offer.maximum_discount_vnd)

                    estimated_reward_vnd += cashback
                    applied_offer_ids.append(offer.id)
                    applied_offer_names.append(offer.display_name)
                    explanation_codes.append("OFFER_APPLIED_CASHBACK")

            amount_debited_vnd = max(0, intent.amount_vnd + fee_vnd - immediate_discount_vnd)
            effective_cost_vnd = max(0, amount_debited_vnd - estimated_reward_vnd)

            # Check balance / credit liquidity
            if source.available_balance_vnd < amount_debited_vnd:
                eligible = False
                eligibility_reasons.append(
                    f"Số dư khả dụng ({source.available_balance_vnd:,}đ) không đủ để thanh toán ({amount_debited_vnd:,}đ)."
                )
                explanation_codes.append("INSUFFICIENT_FUNDS")
            else:
                eligibility_reasons.append("Nguồn tiền khả dụng.")

            if fee_vnd > 0:
                explanation_codes.append("FEE_APPLIED")

            quote_id = str(uuid.uuid4())
            db_quote = PaymentQuote(
                id=quote_id,
                payment_intent_id=intent.id,
                source_account_id=source.id,
                amount_vnd=intent.amount_vnd,
                fee_vnd=fee_vnd,
                immediate_discount_vnd=immediate_discount_vnd,
                amount_debited_vnd=amount_debited_vnd,
                estimated_reward_vnd=estimated_reward_vnd,
                effective_cost_vnd=effective_cost_vnd,
                eligible=eligible,
                eligibility_reason="; ".join(eligibility_reasons),
                applied_offer_ids=applied_offer_ids,
                source_version=1,
                status="ACTIVE",
                expires_at=quote_expiry,
            )
            quote_models.append(db_quote)

            quote_responses.append(
                PaymentQuoteResponse(
                    id=quote_id,
                    payment_intent_id=intent.id,
                    source_account_id=source.id,
                    source_display_name=source.display_name,
                    source_type=source.account_type,
                    amount_vnd=intent.amount_vnd,
                    fee_vnd=fee_vnd,
                    immediate_discount_vnd=immediate_discount_vnd,
                    amount_debited_vnd=amount_debited_vnd,
                    estimated_reward_vnd=estimated_reward_vnd,
                    effective_cost_vnd=effective_cost_vnd,
                    eligible=eligible,
                    eligibility_reason="; ".join(eligibility_reasons),
                    applied_offer_ids=applied_offer_ids,
                    applied_offer_names=applied_offer_names,
                    expires_at=quote_expiry,
                    recommended=False,
                    explanation_codes=explanation_codes,
                )
            )

        # 3. Deterministic Ranking & Tie-breaking
        # Ranking criteria:
        # 1. eligible (True first)
        # 2. effective_cost_vnd (Lowest first)
        # 3. amount_debited_vnd (Lowest first)
        # 4. fee_vnd (Lowest first)
        # 5. source priority (EWALLET > SIMULATED_BANK > SIMULATED_CARD)
        source_prio = {"EWALLET": 1, "SIMULATED_BANK": 2, "SIMULATED_CARD": 3}

        quote_responses.sort(
            key=lambda q: (
                0 if q.eligible else 1,
                q.effective_cost_vnd,
                q.amount_debited_vnd,
                q.fee_vnd,
                source_prio.get(q.source_type, 99),
            )
        )

        recommended_id = quote_responses[0].id if quote_responses else ""
        if quote_responses:
            quote_responses[0].recommended = True
            quote_responses[0].explanation_codes.append("RECOMMENDED_OPTIMAL_SOURCE")

        # Save quotes in DB
        db.add_all(quote_models)
        db.flush()

        best = quote_responses[0] if quote_responses else None
        if best and best.eligible:
            if best.estimated_reward_vnd > 0 or best.immediate_discount_vnd > 0:
                summary = (
                    f"Khuyên dùng '{best.source_display_name}' vì có chi phí hiệu quả thấp nhất "
                    f"({best.effective_cost_vnd:,}đ) nhờ ưu đãi tiết kiệm "
                    f"({best.immediate_discount_vnd + best.estimated_reward_vnd:,}đ)."
                )
            else:
                summary = f"Khuyên dùng '{best.source_display_name}' với phí giao dịch thấp nhất (0đ)."
        elif best and not best.eligible:
            summary = "Không có nguồn tiền nào có đủ số dư để thực hiện giao dịch."
        else:
            summary = "Không tìm thấy nguồn tiền phù hợp."

        return RoutingCalculationResponse(
            payment_intent_id=intent.id,
            amount_vnd=intent.amount_vnd,
            quotes=quote_responses,
            recommended_quote_id=recommended_id,
            recommendation_summary=summary,
            computed_at=now,
        )

