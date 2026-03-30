from __future__ import annotations

import base64
from urllib.parse import quote_plus

import httpx

from app.services.repository.base import RepositoryClient, RepositoryFileWrite


class GitLabRepositoryClient(RepositoryClient):
    def __init__(
        self,
        base_url: str,
        namespace: str,
        repository_name: str,
        token: str,
        default_branch: str = "main",
    ):
        self.base_url = base_url.rstrip("/")
        self.namespace = namespace
        self.repository_name = repository_name
        self.token = token
        self.default_branch = default_branch
        self.project_ref = quote_plus(f"{namespace}/{repository_name}")
        self.api_url = f"{self.base_url}/api/v4/projects/{self.project_ref}"

    def _headers(self) -> dict[str, str]:
        return {
            "PRIVATE-TOKEN": self.token,
        }

    def _request(self, method: str, path: str, **kwargs):
        response = httpx.request(method, f"{self.api_url}{path}", headers=self._headers(), timeout=30.0, **kwargs)
        response.raise_for_status()
        if response.content:
            return response.json()
        return {}

    def ensure_branch(self, branch_name: str, base_branch: str) -> None:
        try:
            self._request("GET", f"/repository/branches/{quote_plus(branch_name)}")
            return
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
        self._request("POST", "/repository/branches", params={"branch": branch_name, "ref": base_branch})

    def list_branches(self) -> list[str]:
        branches = self._request("GET", "/repository/branches")
        return [branch["name"] for branch in branches]

    def read_text(self, rel_path: str, branch_name: str) -> str:
        try:
            response = self._request("GET", f"/repository/files/{quote_plus(rel_path)}", params={"ref": branch_name})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return ""
            raise
        return base64.b64decode(response["content"]).decode("utf-8")

    def read_binary(self, rel_path: str, branch_name: str) -> bytes:
        try:
            response = self._request("GET", f"/repository/files/{quote_plus(rel_path)}", params={"ref": branch_name})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return b""
            raise
        return base64.b64decode(response["content"])

    def list_files(self, rel_path: str, branch_name: str) -> list[str]:
        try:
            tree = self._request(
                "GET",
                "/repository/tree",
                params={"path": rel_path, "ref": branch_name, "recursive": True, "per_page": 1000},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return []
            raise
        return [entry["path"] for entry in tree if entry.get("type") == "blob"]

    def write_files(
        self,
        branch_name: str,
        files: list[RepositoryFileWrite],
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        self.ensure_branch(branch_name, self.default_branch)
        actions = []
        for file in files:
            existing = self.read_binary(file.rel_path, branch_name)
            actions.append(
                {
                    "action": "update" if existing else "create",
                    "file_path": file.rel_path,
                    "content": base64.b64encode(file.content).decode("utf-8"),
                    "encoding": "base64",
                }
            )
        commit = self._request(
            "POST",
            "/repository/commits",
            json={
                "branch": branch_name,
                "commit_message": commit_message,
                "author_name": author_name,
                "author_email": author_email,
                "actions": actions,
            },
        )
        return commit["id"]

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
            return ""
        self.ensure_branch(branch_name, self.default_branch)
        actions = [{"action": "delete", "file_path": rel_path} for rel_path in unique_paths]
        commit = self._request(
            "POST",
            "/repository/commits",
            json={
                "branch": branch_name,
                "commit_message": commit_message,
                "author_name": author_name,
                "author_email": author_email,
                "actions": actions,
            },
        )
        return commit["id"]

    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str) -> dict:
        return self._request(
            "POST",
            "/merge_requests",
            json={
                "title": title,
                "description": body,
                "source_branch": head_branch,
                "target_branch": base_branch,
            },
        )

    def create_issue(self, title: str, body: str) -> dict:
        return self._request("POST", "/issues", json={"title": title, "description": body})
