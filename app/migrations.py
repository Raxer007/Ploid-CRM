from sqlalchemy import inspect, text

from app.database import engine


def run_migrations():
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    is_postgres = engine.dialect.name == "postgresql"
    true_val = "true" if is_postgres else "1"
    false_default = "false" if is_postgres else "0"

    with engine.begin() as conn:
        if "users" in table_names:
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "is_host" not in user_cols:
                conn.execute(
                    text(
                        f"ALTER TABLE users ADD COLUMN is_host BOOLEAN "
                        f"DEFAULT {false_default} NOT NULL"
                    )
                )
                conn.execute(
                    text(
                        f"UPDATE users SET is_host = {true_val} "
                        "WHERE id = (SELECT MIN(id) FROM users)"
                    )
                )
