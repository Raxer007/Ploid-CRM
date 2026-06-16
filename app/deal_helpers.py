import json
from datetime import date, timedelta
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Deal, DealStatus, User


DEAL_STATUS_LABELS = {
    DealStatus.won: "Won",
    DealStatus.pending: "Pending",
    DealStatus.lost: "Lost",
}

DEAL_STATUS_COLORS = {
    DealStatus.won: "bg-emerald-100 text-emerald-800",
    DealStatus.pending: "bg-amber-100 text-amber-800",
    DealStatus.lost: "bg-slate-100 text-slate-600",
}


def format_money(amount: float) -> str:
    return f"${amount:,.2f}"


def parse_amount(value: str) -> float:
    try:
        cleaned = value.replace("$", "").replace(",", "").strip()
        return max(0.0, float(cleaned))
    except (ValueError, TypeError):
        return 0.0


def get_revenue_stats(db: Session) -> Dict[str, Any]:
    today = date.today()
    month_start = today.replace(day=1)

    total_won = (
        db.query(func.coalesce(func.sum(Deal.amount), 0.0))
        .filter(Deal.status == DealStatus.won)
        .scalar()
    )
    month_won = (
        db.query(func.coalesce(func.sum(Deal.amount), 0.0))
        .filter(Deal.status == DealStatus.won, Deal.closed_date >= month_start)
        .scalar()
    )
    pending_value = (
        db.query(func.coalesce(func.sum(Deal.amount), 0.0))
        .filter(Deal.status == DealStatus.pending)
        .scalar()
    )
    deal_count = db.query(Deal).filter(Deal.status == DealStatus.won).count()

    return {
        "total_revenue": float(total_won or 0),
        "month_revenue": float(month_won or 0),
        "pending_value": float(pending_value or 0),
        "won_count": deal_count,
    }


def get_revenue_by_person(db: Session) -> List[Dict[str, Any]]:
    rows = (
        db.query(
            User.id,
            User.name,
            func.coalesce(func.sum(Deal.amount), 0.0),
            func.count(Deal.id),
        )
        .outerjoin(Deal, (Deal.user_id == User.id) & (Deal.status == DealStatus.won))
        .group_by(User.id, User.name)
        .order_by(func.coalesce(func.sum(Deal.amount), 0.0).desc())
        .all()
    )
    return [
        {
            "user_id": r[0],
            "name": r[1],
            "revenue": float(r[2] or 0),
            "deal_count": int(r[3] or 0),
        }
        for r in rows
    ]


def get_revenue_chart_data(db: Session, days: int = 90) -> str:
    end = date.today()
    start = end - timedelta(days=days - 1)
    labels = []
    amounts = []

    current = start
    while current <= end:
        labels.append(current.strftime("%b %d"))
        day_total = (
            db.query(func.coalesce(func.sum(Deal.amount), 0.0))
            .filter(Deal.status == DealStatus.won, Deal.closed_date == current)
            .scalar()
        )
        amounts.append(float(day_total or 0))
        current += timedelta(days=1)

    return json.dumps({"labels": labels, "amounts": amounts})
