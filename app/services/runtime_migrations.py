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

    if "users" in tables:
        existing_columns = {column["name"] for column in inspector.get_columns("users")}
        if "session_version" not in existing_columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1")

    if "invitations" not in tables:
        alter_statements.extend(
            [
                """CREATE TABLE invitations (
                    id SERIAL PRIMARY KEY,
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    email_normalized VARCHAR(255) NOT NULL,
                    organization_id INTEGER NOT NULL REFERENCES organizations(id),
                    membership_role VARCHAR(255) NOT NULL,
                    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
                    created_at TIMESTAMP WITHOUT TIME ZONE,
                    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    used_at TIMESTAMP WITHOUT TIME ZONE,
                    revoked_at TIMESTAMP WITHOUT TIME ZONE,
                    CONSTRAINT ck_invitation_editor CHECK (membership_role = 'editor')
                )""",
                "CREATE INDEX ix_invitations_email_normalized ON invitations (email_normalized)",
            ]
        )

    if "external_identities" not in tables:
        alter_statements.extend(
            [
                """CREATE TABLE external_identities (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    provider VARCHAR(1024) NOT NULL,
                    subject VARCHAR(255) NOT NULL,
                    CONSTRAINT uq_external_identity UNIQUE (provider, subject)
                )""",
            ]
        )

    if "organization_memberships" in tables:
        # Fail closed on ambiguous legacy memberships; never pick a role or
        # delete a duplicate automatically during startup.
        with engine.connect() as connection:
            duplicate = connection.execute(text(
                "SELECT user_id, organization_id FROM organization_memberships "
                "GROUP BY user_id, organization_id HAVING COUNT(*) > 1"
            )).first()
            if duplicate:
                raise RuntimeError("Membresías duplicadas: resolver manualmente antes de arrancar.")
        alter_statements.append(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_membership_user_org "
            "ON organization_memberships (user_id, organization_id)"
        )

    if not alter_statements:
        return

    with engine.begin() as connection:
        for statement in alter_statements:
            connection.execute(text(statement))
