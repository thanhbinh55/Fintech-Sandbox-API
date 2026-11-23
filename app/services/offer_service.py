"""Offer query and eligibility evaluation service."""
from datetime import datetime, timezone
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.models import Offer
from app.schemas.offer import OfferResponse


class OfferService:
    @staticmethod
    def get_offers(db: Session, session_id: str, active_only: bool = True) -> List[OfferResponse]:
        query = select(Offer).where(Offer.demo_session_id == session_id)
        if active_only:
            now = datetime.now(timezone.utc)
            query = query.where(
                Offer.active.is_(True),
                Offer.starts_at <= now,
                Offer.expires_at >= now,
            )
        offers = db.execute(query).scalars().all()
        return [
            OfferResponse(
                id=o.id,
                display_name=o.display_name,
                code=o.code,
                eligible_source_types=o.eligible_source_types or [],
                eligible_merchant_ids=o.eligible_merchant_ids,
                minimum_amount_vnd=o.minimum_amount_vnd,
                maximum_discount_vnd=o.maximum_discount_vnd,
                reward_type=o.reward_type,
                reward_value_percent=float(o.reward_value_percent) if o.reward_value_percent else None,
                reward_value_flat_vnd=o.reward_value_flat_vnd,
                starts_at=o.starts_at,
                expires_at=o.expires_at,
                active=o.active,
            )
            for o in offers
        ]

    @staticmethod
    def get_offer_by_id(db: Session, session_id: str, offer_id: str) -> OfferResponse:
        offer = db.execute(
            select(Offer).where(Offer.id == offer_id, Offer.demo_session_id == session_id)
        ).scalar_one_or_none()
        if not offer:
            raise ResourceNotFoundException("Offer", offer_id)

        return OfferResponse(
            id=offer.id,
            display_name=offer.display_name,
            code=offer.code,
            eligible_source_types=offer.eligible_source_types or [],
            eligible_merchant_ids=offer.eligible_merchant_ids,
            minimum_amount_vnd=offer.minimum_amount_vnd,
            maximum_discount_vnd=offer.maximum_discount_vnd,
            reward_type=offer.reward_type,
            reward_value_percent=float(offer.reward_value_percent) if offer.reward_value_percent else None,
            reward_value_flat_vnd=offer.reward_value_flat_vnd,
            starts_at=offer.starts_at,
            expires_at=offer.expires_at,
            active=offer.active,
        )
