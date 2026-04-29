from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import engine


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    alter_statements: list[str] = []

    if "repository_sources" in tables:
        existing_columns = {column["name"] for column in inspector.get_columns("repository_sources")}
        if "provider_url" not in existing_columns:
            alter_statements.append("ALTER TABLE repository_sources ADD COLUMN provider_url VARCHAR(1024)")
        if "repository_namespace" not in existing_columns:
            alter_statements.append("ALTER TABLE repository_sources ADD COLUMN repository_namespace VARCHAR(255)")
        if "repository_name" not in existing_columns:
            alter_statements.append("ALTER TABLE repository_sources ADD COLUMN repository_name VARCHAR(255)")
        if "service_username" not in existing_columns:
            alter_statements.append("ALTER TABLE repository_sources ADD COLUMN service_username VARCHAR(255)")
        if "service_token" not in existing_columns:
            alter_statements.append("ALTER TABLE repository_sources ADD COLUMN service_token TEXT")

    if "review_requests" in tables:
        existing_columns = {column["name"] for column in inspector.get_columns("review_requests")}
        if "commits_count" not in existing_columns:
            alter_statements.append("ALTER TABLE review_requests ADD COLUMN commits_count INTEGER NOT NULL DEFAULT 0")
        if "comments_count" not in existing_columns:
            alter_statements.append("ALTER TABLE review_requests ADD COLUMN comments_count INTEGER NOT NULL DEFAULT 0")
        if "last_synced_at" not in existing_columns:
            alter_statements.append("ALTER TABLE review_requests ADD COLUMN last_synced_at TIMESTAMP NULL")

    if not alter_statements:
        return

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))
