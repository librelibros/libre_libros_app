from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import engine


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "repository_sources" not in tables:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("repository_sources")}
    alter_statements = []
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

    if not alter_statements:
        return

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))
