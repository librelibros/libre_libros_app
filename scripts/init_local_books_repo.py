from pathlib import Path
import subprocess
import sys


def run(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/init_local_books_repo.py <path>")

    target = Path(sys.argv[1]).resolve()
    target.mkdir(parents=True, exist_ok=True)
    if not (target / ".git").exists():
        run(target, "init", "-b", "main")
    readme = target / "README.md"
    if not readme.exists():
        readme.write_text("# Repositorio de contenidos Libre Libros\n", encoding="utf-8")
        run(target, "add", "README.md")
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Libre Libros",
                "-c",
                "user.email=libre-libros@example.local",
                "commit",
                "-m",
                "Initial content repository",
            ],
            cwd=target,
            check=True,
        )
    print(f"Initialized local repository at {target}")


if __name__ == "__main__":
    main()

