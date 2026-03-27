from __future__ import annotations

import subprocess
from pathlib import Path

from app.services.repository.base import RepositoryClient, RepositoryFileWrite


class LocalGitRepositoryClient(RepositoryClient):
    def __init__(self, repo_path: Path, default_branch: str = "main"):
        self.repo_path = repo_path
        self.default_branch = default_branch
        self.repo_path.mkdir(parents=True, exist_ok=True)
        self._ensure_repo()

    def _run(self, *args: str, check: bool = True) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        return completed.stdout.strip()

    def _ensure_repo(self) -> None:
        if (self.repo_path / ".git").exists():
            return
        self._run("init", "-b", self.default_branch)
        (self.repo_path / "README.md").write_text("# Libre Libros content repo\n", encoding="utf-8")
        self._run("add", "README.md")
        self._run(
            "-c",
            "user.name=Libre Libros",
            "-c",
            "user.email=libre-libros@example.local",
            "commit",
            "-m",
            "Initial content repository",
        )

    def ensure_branch(self, branch_name: str, base_branch: str) -> None:
        existing = self.list_branches()
        if branch_name in existing:
            return
        self._run("checkout", base_branch)
        self._run("checkout", "-b", branch_name)
        self._run("checkout", base_branch)

    def list_branches(self) -> list[str]:
        output = self._run("branch", "--format=%(refname:short)")
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _checkout(self, branch_name: str) -> None:
        self._run("checkout", branch_name)

    def read_text(self, rel_path: str, branch_name: str) -> str:
        try:
            return self._run("show", f"{branch_name}:{rel_path}")
        except RuntimeError:
            target = self.repo_path / rel_path
            if target.exists():
                return target.read_text(encoding="utf-8")
            return ""

    def read_binary(self, rel_path: str, branch_name: str) -> bytes:
        try:
            completed = subprocess.run(
                ["git", "show", f"{branch_name}:{rel_path}"],
                cwd=self.repo_path,
                capture_output=True,
                check=False,
            )
            if completed.returncode == 0:
                return completed.stdout
        except FileNotFoundError:
            pass

        target = self.repo_path / rel_path
        if target.exists():
            return target.read_bytes()
        return b""

    def list_files(self, rel_path: str, branch_name: str) -> list[str]:
        try:
            output = self._run("ls-tree", "-r", "--name-only", branch_name, rel_path)
            files = [line.strip() for line in output.splitlines() if line.strip()]
            if files:
                return files
        except RuntimeError:
            pass
        target = self.repo_path / rel_path
        if not target.exists():
            return []
        return [item.relative_to(self.repo_path).as_posix() for item in target.rglob("*") if item.is_file()]

    def write_files(
        self,
        branch_name: str,
        files: list[RepositoryFileWrite],
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        self.ensure_branch(branch_name, self.default_branch)
        self._checkout(branch_name)
        try:
            for file in files:
                target = self.repo_path / file.rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(file.content)
            self._run("add", *[file.rel_path for file in files])
            commit = subprocess.run(
                [
                    "git",
                    "-c",
                    f"user.name={author_name}",
                    "-c",
                    f"user.email={author_email}",
                    "commit",
                    "-m",
                    commit_message,
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if commit.returncode not in {0, 1}:
                raise RuntimeError(commit.stderr.strip() or commit.stdout.strip())
            return self._run("rev-parse", "HEAD")
        finally:
            self._checkout(self.default_branch)

    def write_text(
        self,
        rel_path: str,
        branch_name: str,
        content: str,
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        return self.write_files(
            branch_name,
            [RepositoryFileWrite(rel_path=rel_path, content=content.encode("utf-8"))],
            commit_message,
            author_name,
            author_email,
        )

    def write_binary(
        self,
        rel_path: str,
        branch_name: str,
        content: bytes,
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        return self.write_files(
            branch_name,
            [RepositoryFileWrite(rel_path=rel_path, content=content)],
            commit_message,
            author_name,
            author_email,
        )

    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str) -> dict:
        return {
            "number": None,
            "url": None,
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "mode": "local-review-request",
        }

    def create_issue(self, title: str, body: str) -> dict:
        return {"number": None, "url": None, "title": title, "body": body, "mode": "local-issue"}
