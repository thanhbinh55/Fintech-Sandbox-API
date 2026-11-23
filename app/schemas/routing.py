"""Smart payment routing and quote ranking schemas."""
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field
from app.schemas.payment import PaymentQuoteResponse


class RoutingCalculationResponse(BaseModel):
    payment_intent_id: str
    amount_vnd: int
    quotes: List[PaymentQuoteResponse]
    recommended_quote_id: str
    recommendation_summary: str
    computed_at: datetime

