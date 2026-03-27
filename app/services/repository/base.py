from __future__ import annotations

from abc import ABC, abstractmethod


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
    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def create_issue(self, title: str, body: str) -> dict:
        raise NotImplementedError

