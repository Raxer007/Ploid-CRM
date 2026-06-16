import json
from datetime import date, timedelta
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import DailyActivity, User


def parse_count(value: str) -> int:
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        return 0


def activity_score(linkedin: int, meetings: int, sales: int) -> int:
    return linkedin + meetings * 2 + sales * 5


def get_or_create_activity(
    db: Session, user_id: int, activity_date: date
) -> DailyActivity:
    record = (
        db.query(DailyActivity)
        .filter(
            DailyActivity.user_id == user_id,
            DailyActivity.activity_date == activity_date,
        )
        .first()
    )
    if not record:
        record = DailyActivity(user_id=user_id, activity_date=activity_date)
        db.add(record)
    return record


def get_team_leaderboard(
    db: Session, start_date: date, end_date: date, current_user_id: int
) -> List[Dict[str, Any]]:
    users = db.query(User).order_by(User.name).all()
    leaderboard = []

    for u in users:
        totals = (
            db.query(
                func.coalesce(func.sum(DailyActivity.linkedin_contacts), 0),
                func.coalesce(func.sum(DailyActivity.meetings_set), 0),
                func.coalesce(func.sum(DailyActivity.sales_closed), 0),
            )
            .filter(
                DailyActivity.user_id == u.id,
                DailyActivity.activity_date >= start_date,
                DailyActivity.activity_date <= end_date,
            )
            .one()
        )
        linkedin, meetings, sales = int(totals[0]), int(totals[1]), int(totals[2])
        leaderboard.append(
            {
                "user_id": u.id,
                "name": u.name,
                "linkedin": linkedin,
                "meetings": meetings,
                "sales": sales,
                "score": activity_score(linkedin, meetings, sales),
                "is_current_user": u.id == current_user_id,
            }
        )

    leaderboard.sort(key=lambda x: (-x["score"], -x["sales"], x["name"].lower()))
    for rank, entry in enumerate(leaderboard, start=1):
        entry["rank"] = rank
    return leaderboard


def get_team_chart_data(db: Session, days: int = 14) -> str:
    end = date.today()
    start = end - timedelta(days=days - 1)
    labels = []
    linkedin_data = []
    meetings_data = []
    sales_data = []

    current = start
    while current <= end:
        labels.append(current.strftime("%b %d"))
        day_totals = (
            db.query(
                func.coalesce(func.sum(DailyActivity.linkedin_contacts), 0),
                func.coalesce(func.sum(DailyActivity.meetings_set), 0),
                func.coalesce(func.sum(DailyActivity.sales_closed), 0),
            )
            .filter(DailyActivity.activity_date == current)
            .one()
        )
        linkedin_data.append(int(day_totals[0]))
        meetings_data.append(int(day_totals[1]))
        sales_data.append(int(day_totals[2]))
        current += timedelta(days=1)

    return json.dumps(
        {
            "labels": labels,
            "linkedin": linkedin_data,
            "meetings": meetings_data,
            "sales": sales_data,
        }
    )


def get_user_chart_data(db: Session, user_id: int, days: int = 14) -> str:
    end = date.today()
    start = end - timedelta(days=days - 1)
    labels = []
    scores = []

    current = start
    while current <= end:
        labels.append(current.strftime("%b %d"))
        record = (
            db.query(DailyActivity)
            .filter(
                DailyActivity.user_id == user_id,
                DailyActivity.activity_date == current,
            )
            .first()
        )
        if record:
            scores.append(record.activity_score)
        else:
            scores.append(0)
        current += timedelta(days=1)

    return json.dumps({"labels": labels, "scores": scores})
