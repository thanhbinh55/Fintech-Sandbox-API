"""Audit event and simulation control schemas."""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    id: str
    actor_type: str
    actor_id: str
    event_type: str
    entity_type: str
    entity_id: str
    metadata: Dict[str, Any]
    created_at: datetime


class SimulateIncomingRequest(BaseModel):
    account_id: str = Field(..., description="Target simulated account ID")
    amount_vnd: int = Field(..., gt=0, description="Amount to deposit in VND")
    sender_description: str = Field(default="Nạp tiền từ ngân hàng liên kết (Sandbox)", description="Deposit narrative")


class SimulateFailureRequest(BaseModel):
    failure_reason: str = Field(default="SIMULATED_NETWORK_TIMEOUT", description="Reason for simulated failure")

