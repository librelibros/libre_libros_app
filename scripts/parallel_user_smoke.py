from __future__ import annotations

import argparse
import sqlite3
import subprocess
import threading
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from slugify import slugify

from journey_support import build_env, build_output_dir, launch_server, prepare_example_repo


DEFAULT_BASE_URL = "http://127.0.0.1:8012"


@dataclass(frozen=True)
class SimulatedUser:
    full_name: str
    email: str
    password: str

    @property
    def branch_name(self) -> str:
        return f"users/{slugify(self.full_name)}"


@dataclass(frozen=True)
class BookTarget:
    book_id: int
    title: str


@dataclass
class FlowResult:
    user: SimulatedUser
    book: BookTarget
    commit_subject: str
    comment_body: str
    branch_name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simula varios docentes editando y comentando en paralelo.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    return parser.parse_args()


def list_books(database_path: Path, *, limit: int = 3) -> list[BookTarget]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "select id, title from books order by id asc limit ?",
            (limit,),
        ).fetchall()
    return [BookTarget(book_id=row[0], title=row[1]) for row in rows]


def build_parallel_markdown(book: BookTarget, user: SimulatedUser, note: str) -> str:
    return (
        f"# {book.title}\n\n"
        f"## Ajuste paralelo de {user.full_name}\n\n"
        f"{note}\n\n"
        "[[columns:2]]\n"
        "### Observacion\n\n"
        f"{user.full_name} deja una pista para la revision final.\n"
        "[[col]]\n"
        "### Siguiente paso\n\n"
        "Validar en aula y compartir feedback.\n"
        "[[/columns]]\n"
    )


def run_user_flow(
    *,
    base_url: str,
    user: SimulatedUser,
    book: BookTarget,
    note: str,
    start_barrier: threading.Barrier,
    comment_barrier: threading.Barrier,
) -> FlowResult:
    comment_body = f"{user.full_name}: {note}"

    with httpx.Client(base_url=base_url, follow_redirects=True, timeout=30.0) as client:
        register = client.post(
            "/register",
            data={
                "full_name": user.full_name,
                "email": user.email,
                "password": user.password,
            },
        )
        register.raise_for_status()
        if "Libros por curso y materia" not in register.text:
            raise RuntimeError(f"Registro incompleto para {user.email}")

        edit_page = client.get(f"/books/{book.book_id}/edit", params={"branch": user.branch_name})
        edit_page.raise_for_status()
        if "Guardar" not in edit_page.text:
            raise RuntimeError(f"El editor no abrio correctamente para {user.email}")

        start_barrier.wait(timeout=10)

        save_response = client.post(
            f"/books/{book.book_id}/edit",
            data={
                "branch_name": user.branch_name,
                "content": build_parallel_markdown(book, user, note),
                "commit_message": "",
            },
        )
        save_response.raise_for_status()
        if f"Cambios guardados en la rama {user.branch_name}." not in save_response.text:
            raise RuntimeError(f"El guardado no confirmo la rama {user.branch_name}")

        comment_barrier.wait(timeout=10)

        comment_response = client.post(
            f"/books/{book.book_id}/comments",
            data={
                "branch_name": user.branch_name,
                "anchor": "revision-final",
                "body": comment_body,
            },
        )
        comment_response.raise_for_status()
        if "Comentario anadido correctamente." not in comment_response.text:
            raise RuntimeError(f"No se pudo registrar el comentario de {user.email}")

        detail_response = client.get(f"/books/{book.book_id}", params={"branch": user.branch_name})
        detail_response.raise_for_status()
        if note not in detail_response.text:
            raise RuntimeError(f"El contenido editado no aparece en la rama {user.branch_name}")
        if comment_body not in detail_response.text:
            raise RuntimeError(f"El comentario no aparece para {user.branch_name}")

    return FlowResult(
        user=user,
        book=book,
        commit_subject=f"Update {book.title} on {user.branch_name}",
        comment_body=comment_body,
        branch_name=user.branch_name,
    )


def write_reports(output_dir: Path, base_url: str, results: list[FlowResult]) -> None:
    run_log = output_dir / "run-log.md"
    report = output_dir / "parallel-report.md"

    lines = [
        "# Parallel User Smoke",
        "",
        f"- Fecha: {date.today().isoformat()}",
        f"- Base URL: `{base_url}`",
        "",
        "## Flujos validados",
        "",
    ]
    for index, result in enumerate(results, start=1):
        lines.append(
            f"{index}. `{result.user.email}` edita `{result.book.title}` en `{result.branch_name}`, guarda con commit automatico y anade comentario."
        )
    run_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report_lines = [
        "# Parallel User Report",
        "",
        f"- Date: {date.today().isoformat()}",
        "- Verdict: APPROVED",
        "",
        "## Summary",
        "",
        "Multiple teachers edited different books on personal branches in parallel, saved successfully, and posted comments without losing branch isolation.",
        "",
        "## Artifacts",
        "",
        "- `run-log.md`",
        "- `parallel-server.log`",
    ]
    report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = build_output_dir("parallel-users")
    example_repo_path = prepare_example_repo(output_dir)
    env = build_env(
        output_dir,
        example_repo_path=example_repo_path,
        db_filename="parallel.db",
        admin_email="admin@parallel.local",
        admin_password="admin12345",
        admin_name="Parallel Admin",
        secret_key="parallel-smoke-secret",
    )
    server_process = None
    log_handle = None

    try:
        server_process, log_handle = launch_server(
            base_url=args.base_url,
            output_dir=output_dir,
            env=env,
            server_log_name="parallel-server.log",
            workers=1,
        )
        books = list_books(output_dir / "parallel.db")
        if len(books) < 3:
            raise RuntimeError("No hay suficientes libros de ejemplo para la simulacion paralela.")

        users = [
            SimulatedUser("Ana Profe", "ana.parallel@validator.local", "profe12345"),
            SimulatedUser("Bruno Profe", "bruno.parallel@validator.local", "profe12345"),
            SimulatedUser("Carla Profe", "carla.parallel@validator.local", "profe12345"),
        ]
        notes = [
            "Secuencia adaptada para trabajo cooperativo y cierre oral.",
            "Version resumida para una sesion de 45 minutos con checkpoints visibles.",
            "Refuerzo visual para alumnado que necesita apoyo guiado por pasos.",
        ]

        start_barrier = threading.Barrier(len(users))
        comment_barrier = threading.Barrier(len(users))
        results: list[FlowResult] = []
        errors: list[BaseException] = []

        def worker(user: SimulatedUser, book: BookTarget, note: str) -> None:
            try:
                results.append(
                    run_user_flow(
                        base_url=args.base_url,
                        user=user,
                        book=book,
                        note=note,
                        start_barrier=start_barrier,
                        comment_barrier=comment_barrier,
                    )
                )
            except BaseException as exc:  # pragma: no cover - integration safeguard
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(user, book, note), daemon=True)
            for user, book, note in zip(users, books, notes, strict=True)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=40)

        if errors:
            raise RuntimeError(str(errors[0]))
        if len(results) != len(users):
            raise RuntimeError("La simulacion paralela no completo todos los flujos.")

        for result in results:
            commit_subject = subprocess.run(
                ["git", "log", "-1", "--pretty=%s", result.branch_name],
                cwd=example_repo_path,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if commit_subject != result.commit_subject:
                raise RuntimeError(
                    f"Commit inesperado en {result.branch_name}: {commit_subject!r} != {result.commit_subject!r}"
                )

        write_reports(output_dir, args.base_url, sorted(results, key=lambda item: item.user.email))
    finally:
        if server_process is not None:
            with suppress(Exception):
                server_process.terminate()
            with suppress(Exception):
                server_process.wait(timeout=10)
        if log_handle is not None:
            with suppress(Exception):
                log_handle.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
