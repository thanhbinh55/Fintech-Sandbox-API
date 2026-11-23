"""Contact schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ContactBase(BaseModel):
    display_name: str
    alias: Optional[str] = None
    phone_number: Optional[str] = None
    recipient_account_id: str
    bank_name: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    display_name: Optional[str] = None
    alias: Optional[str] = None
    phone_number: Optional[str] = None
    bank_name: Optional[str] = None


class ContactResponse(ContactBase):
    id: str
    owner_user_id: str
    created_at: datetime


class ContactSearchResponse(BaseModel):
    query: str
    matches: List[ContactResponse]
    is_ambiguous: bool
    clarification_message: Optional[str] = None
