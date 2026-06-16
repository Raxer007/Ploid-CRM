import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ContactStatus(str, enum.Enum):
    lead = "lead"
    prospect = "prospect"
    customer = "customer"
    inactive = "inactive"


class DealStatus(str, enum.Enum):
    won = "won"
    pending = "pending"
    lost = "lost"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", back_populates="owner", cascade="all, delete-orphan"
    )
    activities: Mapped[list["DailyActivity"]] = relationship(
        "DailyActivity", back_populates="user", cascade="all, delete-orphan"
    )
    deals: Mapped[list["Deal"]] = relationship(
        "Deal", back_populates="owner", cascade="all, delete-orphan"
    )


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80), default="")
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus), default=ContactStatus.lead
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    owner: Mapped["User"] = relationship("User", back_populates="contacts")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class DailyActivity(Base):
    __tablename__ = "daily_activities"
    __table_args__ = (
        UniqueConstraint("user_id", "activity_date", name="uq_user_activity_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    activity_date: Mapped[date] = mapped_column(Date, index=True)
    linkedin_contacts: Mapped[int] = mapped_column(Integer, default=0)
    meetings_set: Mapped[int] = mapped_column(Integer, default=0)
    sales_closed: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="activities")

    @property
    def activity_score(self) -> int:
        return self.linkedin_contacts + self.meetings_set * 2 + self.sales_closed * 5


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    company: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[DealStatus] = mapped_column(Enum(DealStatus), default=DealStatus.won)
    closed_date: Mapped[date] = mapped_column(Date, default=date.today)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship("User", back_populates="deals")
