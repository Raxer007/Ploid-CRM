from datetime import datetime
from typing import Optional, Union

from fastapi import Depends, HTTPException, Request
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_COOKIE = "crm_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 days

_sessions: dict[str, int] = {}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_session(user_id: int) -> str:
    token = pwd_context.hash(f"{user_id}-{datetime.utcnow().isoformat()}")
    token = token.replace("/", "_").replace(".", "-")[:64]
    _sessions[token] = user_id
    return token


def destroy_session(token: Optional[str]) -> None:
    if token and token in _sessions:
        del _sessions[token]


def get_user_id_from_session(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    return _sessions.get(token)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = get_user_id_from_session(token)
    if not user_id:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_user(
    request: Request, db: Session = Depends(get_db)
) -> Union[User, RedirectResponse]:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = get_user_id_from_session(token)
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return user
