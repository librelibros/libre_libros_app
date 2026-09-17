import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_INSECURE_DEFAULT_SECRETS = {"", "change-me-in-production"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LIBRE_LIBROS_",
        extra="ignore",
    )

    app_name: str = "Libre Libros"
    secret_key: str = "change-me-in-production"
    environment: str = "development"
    database_url: str = "sqlite:///./data/libre_libros.db"
    host: str = "0.0.0.0"
    port: int = 8000
    repos_root: Path = Path("data/repos")
    example_repo_path: Path | None = None
    local_repo_prefix: str = "local-"
    max_image_bytes: int = 2 * 1024 * 1024
    max_audio_bytes: int = 2 * 1024 * 1024
    session_cookie_name: str = "libre_libros_session"
    external_auth_only: bool = False
    invitation_only: bool = False
    invitation_ttl_hours: int = Field(default=48, ge=1, le=168)
    invitation_max_per_hour: int = Field(default=30, ge=1)
    csrf_enabled: bool = True
    csrf_check_origin: bool = True
    csrf_require_origin: bool = False
    csrf_allowed_origins: list[str] = Field(default_factory=list)
    session_https_only: bool = False
    session_max_age: int = Field(default=43200, ge=60)
    public_base_url: str | None = None

    init_admin_email: str | None = None
    init_admin_password: str | None = None
    init_admin_name: str = "Admin"
    contact_email: str | None = None

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_server_metadata_url: str = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )
    generic_oidc_enabled: bool = False
    generic_oidc_client_id: str | None = None
    generic_oidc_client_secret: str | None = None
    generic_oidc_server_metadata_url: str | None = None
    generic_oidc_name: str = "Single Sign-On"
    github_oauth_enabled: bool = False
    github_oauth_client_id: str | None = None
    github_oauth_client_secret: str | None = None
    github_oauth_name: str = "GitHub"
    gitlab_enabled: bool = False
    gitlab_url: str | None = None
    gitlab_internal_url: str | None = None
    gitlab_client_id: str | None = None
    gitlab_client_secret: str | None = None
    gitlab_name: str = "GitLab"

    bootstrap_repository_provider: str | None = None
    bootstrap_repository_name: str | None = None
    bootstrap_repository_slug: str | None = None
    bootstrap_repository_url: str | None = None
    bootstrap_repository_namespace: str | None = None
    bootstrap_repository_name_remote: str | None = None
    bootstrap_repository_username: str | None = None
    bootstrap_repository_token: str | None = None
    bootstrap_repository_default_branch: str = "main"
    bootstrap_repository_public: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _enforce_secure_defaults(self) -> "Settings":
        if self.environment.strip().lower() not in {"development", "dev", "test", "testing"} and self.secret_key.strip() in _INSECURE_DEFAULT_SECRETS:
            raise ValueError(
                "LIBRE_LIBROS_SECRET_KEY debe configurarse explícitamente en producción: "
                "la clave por defecto no es válida fuera de desarrollo."
            )
        return self

    @property
    def sqlite_connect_args(self) -> dict[str, bool]:
        if self.database_url.startswith("sqlite"):
            return {"check_same_thread": False}
        return {}


@lru_cache
def get_settings() -> Settings:
    # Demo/tests can explicitly disable dotenv without touching the owner's files.
    env_file = os.environ.get("LIBRE_LIBROS_ENV_FILE", ".env")
    settings = Settings(_env_file=env_file or None)
    settings.repos_root.mkdir(parents=True, exist_ok=True)
    return settings
