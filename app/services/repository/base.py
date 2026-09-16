from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


def validate_repository_path(rel_path: str) -> str:
    """Accept only relative POSIX paths; never normalize away unsafe segments."""
    if (
        not rel_path
        or "\\" in rel_path
        or ":" in rel_path
        or any(ord(char) < 32 or ord(char) == 127 for char in rel_path)
        or any(part in {"", ".", "..", ".git"} for part in rel_path.split("/"))
    ):
        raise ValueError("Ruta de repositorio no válida")
    return rel_path


@dataclass(frozen=True)
class RepositoryFileWrite:
    rel_path: str
    content: bytes


class RepositoryClient(ABC):
    @abstractmethod
    def ensure_branch(self, branch_name: str, base_branch: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_branches(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def read_text(self, rel_path: str, branch_name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def read_binary(self, rel_path: str, branch_name: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def list_files(self, rel_path: str, branch_name: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def write_text(
        self,
        rel_path: str,
        branch_name: str,
        content: str,
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def write_binary(
        self,
        rel_path: str,
        branch_name: str,
        content: bytes,
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def write_files(
        self,
        branch_name: str,
        files: list[RepositoryFileWrite],
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete_files(
        self,
        branch_name: str,
        rel_paths: list[str],
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def create_issue(self, title: str, body: str) -> dict:
        raise NotImplementedError
