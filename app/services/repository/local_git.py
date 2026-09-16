from __future__ import annotations

import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path

from app.services.repository.base import RepositoryClient, RepositoryFileWrite, validate_repository_path

try:  # pragma: no cover - Windows fallback is exercised by import path only
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

_REPO_LOCKS: dict[str, threading.RLock] = {}
_REPO_LOCKS_GUARD = threading.Lock()


class LocalGitRepositoryClient(RepositoryClient):
    def __init__(self, repo_path: Path, default_branch: str = "main"):
        self.repo_path = repo_path
        self.default_branch = default_branch
        self.repo_path.mkdir(parents=True, exist_ok=True)
        resolved_path = str(self.repo_path.resolve())
        with _REPO_LOCKS_GUARD:
            self._lock = _REPO_LOCKS.setdefault(resolved_path, threading.RLock())
        self._lock_file_path = self.repo_path / ".libre-libros.lock"
        self._lock_state = threading.local()
        self._ensure_repo()

    @contextmanager
    def _locked(self):
        with self._lock:
            depth = getattr(self._lock_state, "depth", 0)
            if depth == 0 and fcntl is not None:
                handle = self._lock_file_path.open("a+b")
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                self._lock_state.handle = handle
            self._lock_state.depth = depth + 1
            try:
                yield
            finally:
                next_depth = self._lock_state.depth - 1
                if next_depth == 0:
                    handle = getattr(self._lock_state, "handle", None)
                    if handle is not None and fcntl is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                        handle.close()
                    if hasattr(self._lock_state, "handle"):
                        del self._lock_state.handle
                    del self._lock_state.depth
                else:
                    self._lock_state.depth = next_depth

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
        with self._locked():
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
        with self._locked():
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

    def _read_commit(self, branch_name: str) -> str:
        # Resolve a branch (or immutable commit ID), never a user-supplied Git
        # revision expression or command option. Reads do not touch the checkout.
        if len(branch_name) == 40 and all(char in "0123456789abcdef" for char in branch_name):
            ref = branch_name
        else:
            ref = f"refs/heads/{branch_name}"
            self._run("check-ref-format", ref)
        return self._run("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")

    def _read_tree(self, rel_path: str, branch_name: str) -> list[tuple[str, str]]:
        try:
            validate_repository_path(rel_path)
            commit = self._read_commit(branch_name)
            output = self._run("ls-tree", "-r", "-z", commit, "--", f":(literal){rel_path}")
        except (ValueError, RuntimeError):
            return []
        entries = []
        for entry in output.split("\0"):
            if not entry:
                continue
            metadata, path = entry.split("\t", 1)
            mode, kind, sha = metadata.split()
            # Symlinks (120000) and submodules are not readable assets. Git's
            # tree walk never follows directory symlinks, including cross-book.
            if kind != "blob" or mode not in {"100644", "100755"}:
                continue
            if path != rel_path and not path.startswith(f"{rel_path}/"):
                continue
            try:
                validate_repository_path(path)
            except ValueError:
                continue
            entries.append((path, sha))
        return entries

    def read_text(self, rel_path: str, branch_name: str) -> str:
        return self.read_binary(rel_path, branch_name).decode("utf-8")

    def read_binary(self, rel_path: str, branch_name: str) -> bytes:
        for path, sha in self._read_tree(rel_path, branch_name):
            if path != rel_path:
                continue
            completed = subprocess.run(
                ["git", "cat-file", "blob", sha],
                cwd=self.repo_path,
                capture_output=True,
                check=False,
            )
            if completed.returncode == 0:
                return completed.stdout
        return b""

    def list_files(self, rel_path: str, branch_name: str) -> list[str]:
        return [path for path, _ in self._read_tree(rel_path, branch_name)]

    def write_files(
        self,
        branch_name: str,
        files: list[RepositoryFileWrite],
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        with self._locked():
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

    def delete_files(
        self,
        branch_name: str,
        rel_paths: list[str],
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        unique_paths = [path for path in dict.fromkeys(rel_paths) if path]
        if not unique_paths:
            return self._run("rev-parse", branch_name)
        with self._locked():
            self.ensure_branch(branch_name, self.default_branch)
            self._checkout(branch_name)
            try:
                existing_paths: list[str] = []
                for rel_path in unique_paths:
                    target = self.repo_path / rel_path
                    if target.exists():
                        if target.is_dir():
                            for item in sorted(target.rglob("*"), reverse=True):
                                if item.is_file():
                                    item.unlink()
                            for item in sorted(target.rglob("*"), reverse=True):
                                if item.is_dir():
                                    item.rmdir()
                            target.rmdir()
                        else:
                            target.unlink()
                    existing_paths.append(rel_path)
                self._run("add", "-A", *existing_paths)
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
