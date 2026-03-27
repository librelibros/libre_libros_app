from __future__ import annotations

import base64

import httpx

from app.services.repository.base import RepositoryClient


class GitHubRepositoryClient(RepositoryClient):
    def __init__(self, owner: str, repo: str, token: str, default_branch: str = "main"):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.default_branch = default_branch
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, path: str, **kwargs):
        response = httpx.request(method, f"{self.base_url}{path}", headers=self._headers(), timeout=30.0, **kwargs)
        response.raise_for_status()
        if response.content:
            return response.json()
        return {}

    def _get_ref_sha(self, branch_name: str) -> str:
        ref = self._request("GET", f"/git/ref/heads/{branch_name}")
        return ref["object"]["sha"]

    def ensure_branch(self, branch_name: str, base_branch: str) -> None:
        try:
            self._get_ref_sha(branch_name)
            return
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
        base_sha = self._get_ref_sha(base_branch)
        self._request(
            "POST",
            "/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )

    def list_branches(self) -> list[str]:
        branches = self._request("GET", "/branches")
        return [branch["name"] for branch in branches]

    def read_text(self, rel_path: str, branch_name: str) -> str:
        try:
            response = self._request("GET", f"/contents/{rel_path}?ref={branch_name}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return ""
            raise
        return base64.b64decode(response["content"]).decode("utf-8")

    def read_binary(self, rel_path: str, branch_name: str) -> bytes:
        try:
            response = self._request("GET", f"/contents/{rel_path}?ref={branch_name}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return b""
            raise
        return base64.b64decode(response["content"])

    def _content_sha(self, rel_path: str, branch_name: str) -> str | None:
        try:
            response = self._request("GET", f"/contents/{rel_path}?ref={branch_name}")
            return response["sha"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    def _write(
        self,
        rel_path: str,
        branch_name: str,
        content: bytes,
        commit_message: str,
    ) -> str:
        self.ensure_branch(branch_name, self.default_branch)
        sha = self._content_sha(rel_path, branch_name)
        payload = {
            "message": commit_message,
            "content": base64.b64encode(content).decode("utf-8"),
            "branch": branch_name,
        }
        if sha:
            payload["sha"] = sha
        response = self._request("PUT", f"/contents/{rel_path}", json=payload)
        return response["commit"]["sha"]

    def write_text(
        self,
        rel_path: str,
        branch_name: str,
        content: str,
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        return self._write(rel_path, branch_name, content.encode("utf-8"), commit_message)

    def write_binary(
        self,
        rel_path: str,
        branch_name: str,
        content: bytes,
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        return self._write(rel_path, branch_name, content, commit_message)

    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str) -> dict:
        return self._request(
            "POST",
            "/pulls",
            json={"title": title, "body": body, "head": head_branch, "base": base_branch},
        )

    def create_issue(self, title: str, body: str) -> dict:
        return self._request("POST", "/issues", json={"title": title, "body": body})
