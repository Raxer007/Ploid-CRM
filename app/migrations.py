from sqlalchemy import inspect, text

from app.database import engine


def run_migrations():
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    with engine.begin() as conn:
        if "users" in table_names:
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "is_host" not in user_cols:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN is_host BOOLEAN DEFAULT 0 NOT NULL")
                )
                conn.execute(
                    text(
                        "UPDATE users SET is_host = 1 WHERE id = (SELECT MIN(id) FROM users)"
                    )
                )
