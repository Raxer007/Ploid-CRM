from typing import Optional

from sqlalchemy.orm import Session

from app.models import Contact, User


def get_contact_for_user(db: Session, contact_id: int, user: User) -> Optional[Contact]:
    query = db.query(Contact).filter(Contact.id == contact_id)
    if not user.is_host:
        query = query.filter(Contact.user_id == user.id)
    return query.first()


def can_edit_contact(user: User, contact: Contact) -> bool:
    return contact.user_id == user.id
