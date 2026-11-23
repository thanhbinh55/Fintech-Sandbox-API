"""Demo session schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DemoSessionCreate(BaseModel):
    scenario: str = Field(default="scenario_a", description="Seed scenario: scenario_a, scenario_b, scenario_c")
    display_name: Optional[str] = Field(default=None, description="Optional custom session label")


class SessionCredentials(BaseModel):
    user_token: str = Field(..., description="Token scoped for human-in-the-loop user actions (approval, execution)")
    agent_token: str = Field(..., description="Token scoped for AI Copilot function calling (safe reads, quotes, drafts)")
    demo_control_token: str = Field(..., description="Token scoped for administrative session operations & resets")


class DemoSessionResponse(BaseModel):
    id: str
    display_name: str
    seed_scenario: str
    seed_version: str
    status: str
    created_at: datetime
    expires_at: datetime
    credentials: Optional[SessionCredentials] = None
    simulation_notice: str = "ALL BALANCES AND TRANSACTIONS ARE FICTIONAL SANDBOX DATA FOR EVALUATION PURPOSES ONLY."
