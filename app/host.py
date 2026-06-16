import os
from typing import Optional

from sqlalchemy.orm import Session

from app.models import User


def get_host_email() -> Optional[str]:
    email = os.environ.get("HOST_EMAIL", "").strip().lower()
    return email or None


def ensure_host(db: Session, user: Optional[User] = None) -> None:
    host_email = get_host_email()

    if host_email:
        host_user = db.query(User).filter(User.email == host_email).first()
        if host_user and not host_user.is_host:
            db.query(User).filter(User.is_host.is_(True)).update(
                {User.is_host: False}, synchronize_session=False
            )
            host_user.is_host = True
            db.commit()
        return

    has_host = db.query(User).filter(User.is_host.is_(True)).first()
    if has_host:
        return

    target = user or db.query(User).order_by(User.id).first()
    if target:
        target.is_host = True
        db.commit()


def should_be_host_on_register(db: Session, email: str) -> bool:
    host_email = get_host_email()
    if host_email:
        return email.strip().lower() == host_email
    return db.query(User).filter(User.is_host.is_(True)).count() == 0
