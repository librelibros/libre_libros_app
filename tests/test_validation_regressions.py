from pathlib import Path
import subprocess

from scripts.journey_support import prepare_example_repo


REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_REPO = REPO_ROOT / "data" / "repo"
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
