"""Configuration validation without dotenv, database or application startup."""

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("environment", ["production", "prod"])
@pytest.mark.parametrize("secret_key", ["", "change-me-in-production"])
def test_production_rejects_default_session_secret(environment, secret_key):
    with pytest.raises(ValidationError, match="LIBRE_LIBROS_SECRET_KEY"):
        Settings(_env_file=None, environment=environment, secret_key=secret_key)


def test_production_accepts_explicit_session_secret_without_name_error():
    settings = Settings(
        _env_file=None,
        environment="production",
        secret_key="isolated-test-key-not-a-real-production-secret",
    )
    assert settings.is_production
