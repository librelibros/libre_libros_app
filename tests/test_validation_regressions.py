from pathlib import Path
import subprocess

import pytest

from scripts.journey_support import SEED_REPO, build_env, prepare_example_repo

LENGUA_PRIMARIA_BOOK = SEED_REPO / "books" / "primaria" / "lengua" / "lengua-primaria" / "book.md"


def test_prepare_example_repo_creates_an_isolated_copy(tmp_path: Path):
    source_before = LENGUA_PRIMARIA_BOOK.read_text(encoding="utf-8")

    copied_repo = prepare_example_repo(tmp_path)
    copied_book = copied_repo / "books" / "primaria" / "lengua" / "lengua-primaria" / "book.md"
    copied_status = subprocess.run(
        ["git", "-C", str(copied_repo), "status", "--short"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    copied_book.write_text("# Libro temporal de prueba\n", encoding="utf-8")

    assert copied_status == ""
    assert copied_book.read_text(encoding="utf-8") == "# Libro temporal de prueba\n"
    assert LENGUA_PRIMARIA_BOOK.read_text(encoding="utf-8") == source_before


def test_seed_lengua_primaria_book_has_no_validation_artifacts() -> None:
    contents = LENGUA_PRIMARIA_BOOK.read_text(encoding="utf-8")

    forbidden_markers = [
        "Texto de la primera columna para la prueba de exportacion",
        "Texto de la segunda columna con apoyo visual",
        r"\[\[columns:2\]\]",
        "asset.gitkeep",
        "Escribe aquí el contenido de la columna 1.",
        "Escribe aquí el contenido de la columna 2.",
    ]

    for marker in forbidden_markers:
        assert marker not in contents


def test_build_env_discards_inherited_app_and_supabase_settings(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LIBRE_LIBROS_GITHUB_OAUTH_ENABLED", "true")
    monkeypatch.setenv("LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_TOKEN", "fake-parent-token")
    monkeypatch.setenv("LIBRE_LIBROS_UNKNOWN_SETTING", "fake-parent-value")
    monkeypatch.setenv("SUPABASE_URL", "https://do-not-contact.invalid")
    env = build_env(
        tmp_path,
        example_repo_path=tmp_path / "example-repo",
        db_filename="isolated.db",
        admin_email="test@example.invalid",
        admin_password="test-only-password",
        admin_name="Test",
        secret_key="test-only-secret",
    )
    assert env["LIBRE_LIBROS_ENV_FILE"] == ""
    assert env["LIBRE_LIBROS_GITHUB_OAUTH_ENABLED"] == "false"
    assert env["LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_PROVIDER"] == "local"
    assert "LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_TOKEN" not in env
    assert "LIBRE_LIBROS_UNKNOWN_SETTING" not in env
    assert not any(key.startswith("SUPABASE_") for key in env)
    assert env["LIBRE_LIBROS_DATABASE_URL"] == f"sqlite:///{tmp_path / 'isolated.db'}"
    assert Path(env["TMPDIR"]).is_relative_to(tmp_path)


def test_settings_do_not_load_dotenv(tmp_path: Path, monkeypatch):
    from app.config import Settings, get_settings

    # Synthetic, non-secret file: never open the owner's dotenv for this test.
    (tmp_path / ".env").write_text(
        "LIBRE_LIBROS_CONTACT_EMAIL=dotenv-must-not-load@example.invalid\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    assert Settings().contact_email is None
    assert get_settings().contact_email is None
    monkeypatch.setenv("LIBRE_LIBROS_CONTACT_EMAIL", "explicit-test@example.invalid")
    get_settings.cache_clear()
    assert get_settings().contact_email == "explicit-test@example.invalid"


def test_external_network_is_blocked_but_loopback_dns_is_allowed():
    import socket

    with pytest.raises(AssertionError, match="External network"):
        socket.getaddrinfo("must-not-resolve.invalid", 443)
    with socket.socket() as connection:
        with pytest.raises(AssertionError, match="External network"):
            connection.connect(("192.0.2.1", 443))
    assert socket.getaddrinfo("127.0.0.1", 80)


def test_journey_output_rejects_paths_outside_test_plan(tmp_path: Path):
    with pytest.raises(ValueError, match="inside test_plan"):
        prepare_example_repo(tmp_path.parents[4] / "not-test-output")


def test_journey_subprocess_disables_dotenv(tmp_path: Path):
    from scripts.journey_support import PROJECT_DIR
    import json
    import sys

    (tmp_path / ".env").write_text(
        "LIBRE_LIBROS_CONTACT_EMAIL=dotenv-must-not-load@example.invalid\n",
        encoding="utf-8",
    )
    env = build_env(
        tmp_path,
        example_repo_path=tmp_path / "example-repo",
        db_filename="subprocess.db",
        admin_email="test@example.invalid",
        admin_password="test-only-password",
        admin_name="Test",
        secret_key="test-only-secret",
    )
    result = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, {str(PROJECT_DIR)!r}); "
         "from app.config import get_settings; import json; "
         "print(json.dumps({'contact': get_settings().contact_email, "
         "'database': get_settings().database_url}))"],
        cwd=tmp_path, env=env, check=True, capture_output=True, text=True,
    )
    assert json.loads(result.stdout) == {
        "contact": None,
        "database": f"sqlite:///{tmp_path / 'subprocess.db'}",
    }
