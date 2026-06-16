from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.access import can_edit_contact, get_contact_for_user
from app.activity_helpers import (
    get_or_create_activity,
    get_team_chart_data,
    get_team_leaderboard,
    get_user_chart_data,
    parse_count,
)
from app.auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session,
    destroy_session,
    hash_password,
    require_user,
    verify_password,
)
from app.deal_helpers import (
    DEAL_STATUS_COLORS,
    DEAL_STATUS_LABELS,
    format_money,
    get_revenue_by_person,
    get_revenue_chart_data,
    get_revenue_stats,
    parse_amount,
)
from app.database import Base, SessionLocal, engine, get_db
from app.host import ensure_host, should_be_host_on_register
from app.migrations import run_migrations
from app.models import Contact, ContactStatus, DailyActivity, Deal, DealStatus, User

app = FastAPI(title="Team CRM")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

Base.metadata.create_all(bind=engine)
run_migrations()
with SessionLocal() as db:
    ensure_host(db)

STATUS_LABELS = {
    ContactStatus.lead: "Lead",
    ContactStatus.prospect: "Prospect",
    ContactStatus.customer: "Customer",
    ContactStatus.inactive: "Inactive",
}

STATUS_COLORS = {
    ContactStatus.lead: "bg-blue-100 text-blue-800",
    ContactStatus.prospect: "bg-amber-100 text-amber-800",
    ContactStatus.customer: "bg-emerald-100 text-emerald-800",
    ContactStatus.inactive: "bg-slate-100 text-slate-600",
}


def template_context(request: Request, user: User, **extra):
    return {
        "request": request,
        "user": user,
        "status_labels": STATUS_LABELS,
        "status_colors": STATUS_COLORS,
        "statuses": list(ContactStatus),
        "deal_status_labels": DEAL_STATUS_LABELS,
        "deal_status_colors": DEAL_STATUS_COLORS,
        "deal_statuses": list(DealStatus),
        "format_money": format_money,
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        "auth.html",
        {
            "request": request,
            "mode": "register",
            "title": "Create account",
            "error": None,
        },
    )


@app.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse(
            "auth.html",
            {
                "request": request,
                "mode": "register",
                "title": "Create account",
                "error": "An account with this email already exists.",
                "name": name,
                "email": email,
            },
            status_code=400,
        )
    if len(password) < 6:
        return templates.TemplateResponse(
            "auth.html",
            {
                "request": request,
                "mode": "register",
                "title": "Create account",
                "error": "Password must be at least 6 characters.",
                "name": name,
                "email": email,
            },
            status_code=400,
        )

    is_host = should_be_host_on_register(db, email)
    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(password),
        is_host=is_host,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_session(user.id)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax"
    )
    return response


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        "auth.html",
        {
            "request": request,
            "mode": "login",
            "title": "Sign in",
            "error": None,
        },
    )


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        return templates.TemplateResponse(
            "auth.html",
            {
                "request": request,
                "mode": "login",
                "title": "Sign in",
                "error": "No account found with that email. Click Create account below.",
                "email": email,
            },
            status_code=400,
        )
    if not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth.html",
            {
                "request": request,
                "mode": "login",
                "title": "Sign in",
                "error": "Incorrect password. Try again or create a new account.",
                "email": email,
            },
            status_code=400,
        )

    ensure_host(db, user)

    token = create_session(user.id)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax"
    )
    return response


@app.post("/logout")
def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    destroy_session(token)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    today_activity = (
        db.query(DailyActivity)
        .filter(
            DailyActivity.user_id == user.id,
            DailyActivity.activity_date == today,
        )
        .first()
    )

    total = db.query(Contact).filter(Contact.user_id == user.id).count()

    leaderboard = get_team_leaderboard(db, week_start, today, user.id)
    team_chart_json = get_team_chart_data(db, 14)
    user_chart_json = get_user_chart_data(db, user.id, 14)

    week_totals = next(
        (e for e in leaderboard if e["is_current_user"]),
        {"linkedin": 0, "meetings": 0, "sales": 0, "score": 0},
    )

    return templates.TemplateResponse(
        "dashboard.html",
        template_context(
            request,
            user,
            total=total,
            today_activity=today_activity,
            today=today,
            leaderboard=leaderboard,
            team_chart_json=team_chart_json,
            user_chart_json=user_chart_json,
            week_totals=week_totals,
        ),
    )


@app.get("/activity", response_class=HTMLResponse)
def activity_page(
    request: Request,
    day: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    if day:
        try:
            selected_date = date.fromisoformat(day)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    record = (
        db.query(DailyActivity)
        .filter(
            DailyActivity.user_id == user.id,
            DailyActivity.activity_date == selected_date,
        )
        .first()
    )

    history = (
        db.query(DailyActivity)
        .filter(DailyActivity.user_id == user.id)
        .order_by(DailyActivity.activity_date.desc())
        .limit(14)
        .all()
    )

    return templates.TemplateResponse(
        "activity.html",
        template_context(
            request,
            user,
            selected_date=selected_date,
            record=record,
            history=history,
            today=date.today(),
            error=None,
        ),
    )


@app.post("/activity")
def activity_save(
    request: Request,
    activity_date: str = Form(...),
    linkedin_contacts: str = Form("0"),
    meetings_set: str = Form("0"),
    sales_closed: str = Form("0"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    try:
        selected_date = date.fromisoformat(activity_date)
    except ValueError:
        selected_date = date.today()

    if selected_date > date.today():
        history = (
            db.query(DailyActivity)
            .filter(DailyActivity.user_id == user.id)
            .order_by(DailyActivity.activity_date.desc())
            .limit(14)
            .all()
        )
        return templates.TemplateResponse(
            "activity.html",
            template_context(
                request,
                user,
                selected_date=selected_date,
                record=None,
                history=history,
                today=date.today(),
                error="You can't log activity for a future date.",
                form={
                    "linkedin_contacts": linkedin_contacts,
                    "meetings_set": meetings_set,
                    "sales_closed": sales_closed,
                    "notes": notes,
                },
            ),
            status_code=400,
        )

    record = get_or_create_activity(db, user.id, selected_date)
    record.linkedin_contacts = parse_count(linkedin_contacts)
    record.meetings_set = parse_count(meetings_set)
    record.sales_closed = parse_count(sales_closed)
    record.notes = notes.strip() or None
    record.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(f"/activity?day={selected_date.isoformat()}", status_code=303)


@app.get("/contacts", response_class=HTMLResponse)
def contacts_list(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    query = db.query(Contact).filter(Contact.user_id == user.id)

    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Contact.first_name.ilike(term),
                Contact.last_name.ilike(term),
                Contact.email.ilike(term),
                Contact.company.ilike(term),
                Contact.phone.ilike(term),
            )
        )

    if status and status in ContactStatus.__members__:
        query = query.filter(Contact.status == ContactStatus(status))

    contacts = query.order_by(Contact.updated_at.desc()).all()

    return templates.TemplateResponse(
        "contacts.html",
        template_context(
            request,
            user,
            contacts=contacts,
            search=q or "",
            filter_status=status or "",
        ),
    )


@app.get("/contacts/new", response_class=HTMLResponse)
def contact_new_page(request: Request, db: Session = Depends(get_db)):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    return templates.TemplateResponse(
        "contact_form.html",
        template_context(request, result, contact=None, error=None),
    )


@app.post("/contacts/new")
def contact_create(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    company: str = Form(""),
    job_title: str = Form(""),
    status: str = Form("lead"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    if not first_name.strip():
        return templates.TemplateResponse(
            "contact_form.html",
            template_context(
                request,
                user,
                contact=None,
                error="First name is required.",
                form={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "phone": phone,
                    "company": company,
                    "job_title": job_title,
                    "status": status,
                    "notes": notes,
                },
            ),
            status_code=400,
        )

    contact_status = (
        ContactStatus(status)
        if status in ContactStatus.__members__
        else ContactStatus.lead
    )

    contact = Contact(
        user_id=user.id,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip() or None,
        phone=phone.strip() or None,
        company=company.strip() or None,
        job_title=job_title.strip() or None,
        status=contact_status,
        notes=notes.strip() or None,
    )
    db.add(contact)
    db.commit()
    return RedirectResponse("/contacts", status_code=303)


@app.get("/contacts/{contact_id}", response_class=HTMLResponse)
def contact_detail(
    contact_id: int, request: Request, db: Session = Depends(get_db)
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    contact = get_contact_for_user(db, contact_id, user)
    if not contact:
        return RedirectResponse("/contacts", status_code=303)

    return templates.TemplateResponse(
        "contact_detail.html",
        template_context(
            request,
            user,
            contact=contact,
            can_edit=can_edit_contact(user, contact),
        ),
    )


@app.get("/contacts/{contact_id}/edit", response_class=HTMLResponse)
def contact_edit_page(
    contact_id: int, request: Request, db: Session = Depends(get_db)
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    contact = get_contact_for_user(db, contact_id, user)
    if not contact or not can_edit_contact(user, contact):
        return RedirectResponse("/contacts", status_code=303)

    return templates.TemplateResponse(
        "contact_form.html",
        template_context(request, user, contact=contact, error=None),
    )


@app.post("/contacts/{contact_id}/edit")
def contact_update(
    contact_id: int,
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    company: str = Form(""),
    job_title: str = Form(""),
    status: str = Form("lead"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    contact = get_contact_for_user(db, contact_id, user)
    if not contact or not can_edit_contact(user, contact):
        return RedirectResponse("/contacts", status_code=303)

    contact.first_name = first_name.strip()
    contact.last_name = last_name.strip()
    contact.email = email.strip() or None
    contact.phone = phone.strip() or None
    contact.company = company.strip() or None
    contact.job_title = job_title.strip() or None
    contact.status = (
        ContactStatus(status)
        if status in ContactStatus.__members__
        else ContactStatus.lead
    )
    contact.notes = notes.strip() or None
    contact.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(f"/contacts/{contact_id}", status_code=303)


@app.post("/contacts/{contact_id}/delete")
def contact_delete(
    contact_id: int, request: Request, db: Session = Depends(get_db)
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    contact = get_contact_for_user(db, contact_id, user)
    if contact and can_edit_contact(user, contact):
        db.delete(contact)
        db.commit()
    return RedirectResponse("/contacts", status_code=303)


@app.get("/deals", response_class=HTMLResponse)
def deals_list(request: Request, db: Session = Depends(get_db)):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    deals = (
        db.query(Deal)
        .order_by(Deal.closed_date.desc(), Deal.created_at.desc())
        .all()
    )
    owners = {u.id: u.name for u in db.query(User).all()}
    stats = get_revenue_stats(db)
    by_person = get_revenue_by_person(db)
    chart_json = get_revenue_chart_data(db, 90)

    return templates.TemplateResponse(
        "deals.html",
        template_context(
            request,
            user,
            deals=deals,
            owners=owners,
            stats=stats,
            by_person=by_person,
            chart_json=chart_json,
        ),
    )


@app.get("/deals/new", response_class=HTMLResponse)
def deal_new_page(request: Request, db: Session = Depends(get_db)):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    return templates.TemplateResponse(
        "deal_form.html",
        template_context(request, result, deal=None, error=None, today=date.today()),
    )


@app.post("/deals/new")
def deal_create(
    request: Request,
    title: str = Form(...),
    amount: str = Form("0"),
    company: str = Form(""),
    status: str = Form("won"),
    closed_date: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    if not title.strip():
        return templates.TemplateResponse(
            "deal_form.html",
            template_context(
                request,
                user,
                deal=None,
                error="Deal name is required.",
                today=date.today(),
                form={
                    "title": title,
                    "amount": amount,
                    "company": company,
                    "status": status,
                    "closed_date": closed_date,
                    "notes": notes,
                },
            ),
            status_code=400,
        )

    try:
        deal_date = date.fromisoformat(closed_date)
    except ValueError:
        deal_date = date.today()

    deal = Deal(
        user_id=user.id,
        title=title.strip(),
        amount=parse_amount(amount),
        company=company.strip() or None,
        status=DealStatus(status) if status in DealStatus.__members__ else DealStatus.won,
        closed_date=deal_date,
        notes=notes.strip() or None,
    )
    db.add(deal)
    db.commit()
    return RedirectResponse("/deals", status_code=303)


@app.get("/deals/{deal_id}/edit", response_class=HTMLResponse)
def deal_edit_page(deal_id: int, request: Request, db: Session = Depends(get_db)):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    deal = db.query(Deal).filter(Deal.id == deal_id, Deal.user_id == user.id).first()
    if not deal:
        return RedirectResponse("/deals", status_code=303)

    return templates.TemplateResponse(
        "deal_form.html",
        template_context(request, user, deal=deal, error=None, today=date.today()),
    )


@app.post("/deals/{deal_id}/edit")
def deal_update(
    deal_id: int,
    request: Request,
    title: str = Form(...),
    amount: str = Form("0"),
    company: str = Form(""),
    status: str = Form("won"),
    closed_date: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    deal = db.query(Deal).filter(Deal.id == deal_id, Deal.user_id == user.id).first()
    if not deal:
        return RedirectResponse("/deals", status_code=303)

    try:
        deal_date = date.fromisoformat(closed_date)
    except ValueError:
        deal_date = date.today()

    deal.title = title.strip()
    deal.amount = parse_amount(amount)
    deal.company = company.strip() or None
    deal.status = DealStatus(status) if status in DealStatus.__members__ else DealStatus.won
    deal.closed_date = deal_date
    deal.notes = notes.strip() or None
    db.commit()
    return RedirectResponse("/deals", status_code=303)


@app.post("/deals/{deal_id}/delete")
def deal_delete(deal_id: int, request: Request, db: Session = Depends(get_db)):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result

    deal = db.query(Deal).filter(Deal.id == deal_id, Deal.user_id == user.id).first()
    if deal:
        db.delete(deal)
        db.commit()
    return RedirectResponse("/deals", status_code=303)


@app.get("/admin/contacts", response_class=HTMLResponse)
def admin_contacts_list(
    request: Request,
    q: Optional[str] = Query(None),
    owner: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    result = require_user(request, db)
    if isinstance(result, RedirectResponse):
        return result
    user = result
    if not user.is_host:
        return RedirectResponse("/contacts", status_code=303)

    query = db.query(Contact).join(User, Contact.user_id == User.id)

    if owner:
        query = query.filter(Contact.user_id == owner)

    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Contact.first_name.ilike(term),
                Contact.last_name.ilike(term),
                Contact.email.ilike(term),
                Contact.company.ilike(term),
                User.name.ilike(term),
            )
        )

    contacts = query.order_by(Contact.updated_at.desc()).all()
    team_members = db.query(User).order_by(User.name).all()
    owners = {u.id: u.name for u in team_members}

    return templates.TemplateResponse(
        "admin_contacts.html",
        template_context(
            request,
            user,
            contacts=contacts,
            owners=owners,
            team_members=team_members,
            search=q or "",
            filter_owner=owner or "",
        ),
    )
