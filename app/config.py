from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LIBRE_LIBROS_",
        extra="ignore",
    )

    app_name: str = "Libre Libros"
    secret_key: str = "change-me-in-production"
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

    init_admin_email: str | None = None
    init_admin_password: str | None = None
    init_admin_name: str = "Admin"

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
    def sqlite_connect_args(self) -> dict[str, bool]:
        if self.database_url.startswith("sqlite"):
            return {"check_same_thread": False}
        return {}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.repos_root.mkdir(parents=True, exist_ok=True)
    return settings
