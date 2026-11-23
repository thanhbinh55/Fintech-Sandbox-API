"""Contact search and recipient resolution service."""
from typing import List, Optional
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.models import Contact
from app.schemas.contact import ContactCreate, ContactResponse, ContactSearchResponse, ContactUpdate


class ContactService:
    @staticmethod
    def search_contacts(
        db: Session, session_id: str, user_id: str, query: str
    ) -> ContactSearchResponse:
        q_clean = query.strip()
        search_filter = or_(
            Contact.display_name.ilike(f"%{q_clean}%"),
            Contact.alias.ilike(f"%{q_clean}%"),
            Contact.phone_number.ilike(f"%{q_clean}%"),
        )
        query_stmt = (
            select(Contact)
            .where(
                Contact.demo_session_id == session_id,
                Contact.owner_user_id == user_id,
                search_filter,
            )
            .order_by(Contact.display_name.asc())
        )
        contacts = db.execute(query_stmt).scalars().all()

        matches = [
            ContactResponse(
                id=c.id,
                owner_user_id=c.owner_user_id,
                display_name=c.display_name,
                alias=c.alias,
                phone_number=c.phone_number,
                recipient_account_id=c.recipient_account_id,
                bank_name=c.bank_name,
                created_at=c.created_at,
            )
            for c in contacts
        ]

        is_ambiguous = len(matches) > 1
        clarification_msg = None
        if is_ambiguous:
            names = ", ".join(f"'{m.display_name}' ({m.alias or m.phone_number})" for m in matches)
            clarification_msg = (
                f"Tìm thấy {len(matches)} người nhận phù hợp với từ khóa '{query}': {names}. "
                f"Vui lòng chỉ định rõ người nhận bạn muốn chuyển tiền."
            )

        return ContactSearchResponse(
            query=query,
            matches=matches,
            is_ambiguous=is_ambiguous,
            clarification_message=clarification_msg,
        )

    @staticmethod
    def get_contact_by_id(
        db: Session, session_id: str, user_id: str, contact_id: str
    ) -> ContactResponse:
        contact = db.execute(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.demo_session_id == session_id,
                Contact.owner_user_id == user_id,
            )
        ).scalar_one_or_none()

        if not contact:
            raise ResourceNotFoundException("Contact", contact_id)

        return ContactResponse(
            id=contact.id,
            owner_user_id=contact.owner_user_id,
            display_name=contact.display_name,
            alias=contact.alias,
            phone_number=contact.phone_number,
            recipient_account_id=contact.recipient_account_id,
            bank_name=contact.bank_name,
            created_at=contact.created_at,
        )

    @staticmethod
    def create_contact(
        db: Session, session_id: str, user_id: str, req: ContactCreate
    ) -> ContactResponse:
        contact = Contact(
            demo_session_id=session_id,
            owner_user_id=user_id,
            display_name=req.display_name,
            alias=req.alias,
            phone_number=req.phone_number,
            recipient_account_id=req.recipient_account_id,
            bank_name=req.bank_name,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)

        return ContactResponse(
            id=contact.id,
            owner_user_id=contact.owner_user_id,
            display_name=contact.display_name,
            alias=contact.alias,
            phone_number=contact.phone_number,
            recipient_account_id=contact.recipient_account_id,
            bank_name=contact.bank_name,
            created_at=contact.created_at,
        )

