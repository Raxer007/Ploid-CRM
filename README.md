# Team CRM

A simple, personal CRM for you and your team. Each person gets their own account and dashboard — contacts you add are private to you.

## Features

- **Personal accounts** — everyone on the team signs up with their own email
- **Private contacts** — you only see contacts you created
- **Daily activity tracking** — log LinkedIn contacts, meetings set, and sales closed each day
- **Team leaderboard** — weekly rankings visible to everyone on the home page
- **Progress charts** — 14-day team and personal activity graphs
- **Contact management** — add, edit, view, delete, search, and filter by status
- **Statuses** — Lead, Prospect, Customer, Inactive

## Quick start

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run the app
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000), create an account, and start adding contacts.

## For your team

Share the server URL with teammates. Each person creates their own account — no shared login needed. Data is stored locally in `crm.db`.

To run on your network so others can access it:

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then share `http://YOUR-IP:8000` with your team.

## Tech stack

- Python + FastAPI
- SQLite (no external database setup)
- Tailwind CSS
