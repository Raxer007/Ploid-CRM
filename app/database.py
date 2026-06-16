import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _normalize_db_url(url: str) -> str:
    # Render/Heroku hand out "postgres://" but SQLAlchemy needs "postgresql://"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = _normalize_db_url(DATABASE_URL)
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
else:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./crm.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
