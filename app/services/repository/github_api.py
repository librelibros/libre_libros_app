from __future__ import annotations

import base64
from urllib.parse import quote

import httpx

from app.services.repository.base import RepositoryClient, RepositoryFileWrite


class GitHubRepositoryClient(RepositoryClient):
    def __init__(self, owner: str, repo: str, token: str | None, default_branch: str = "main", api_url: str | None = None):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.default_branch = default_branch
        api_root = (api_url or "https://api.github.com").rstrip("/")
        self.public_raw_url = None if api_url else f"https://raw.githubusercontent.com/{owner}/{repo}"
        if api_root.endswith("/api/v3"):
            self.base_url = f"{api_root}/repos/{owner}/{repo}"
        else:
            self.base_url = f"{api_root}/repos/{owner}/{repo}"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

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
        if not self.token and self.public_raw_url:
            encoded_path = quote(rel_path)
            response = httpx.get(f"{self.public_raw_url}/{branch_name}/{encoded_path}", timeout=30.0)
            if response.status_code == 404:
                return ""
            response.raise_for_status()
            return response.text
        try:
            response = self._request("GET", f"/contents/{rel_path}?ref={branch_name}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return ""
            raise
        return base64.b64decode(response["content"]).decode("utf-8")

    def read_binary(self, rel_path: str, branch_name: str) -> bytes:
        if not self.token and self.public_raw_url:
            encoded_path = quote(rel_path)
            response = httpx.get(f"{self.public_raw_url}/{branch_name}/{encoded_path}", timeout=30.0)
            if response.status_code == 404:
                return b""
            response.raise_for_status()
            return response.content
        try:
            response = self._request("GET", f"/contents/{rel_path}?ref={branch_name}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return b""
            raise
        return base64.b64decode(response["content"])

    def list_files(self, rel_path: str, branch_name: str) -> list[str]:
        try:
            tree = self._request("GET", f"/git/trees/{branch_name}?recursive=1")
            prefix = rel_path.strip("/")
            return [
                item["path"]
                for item in tree.get("tree", [])
                if item.get("type") == "blob" and (not prefix or item["path"] == prefix or item["path"].startswith(f"{prefix}/"))
            ]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {404, 409}:
                raise

        try:
            response = self._request("GET", f"/contents/{rel_path}?ref={branch_name}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return []
            raise
        if isinstance(response, dict):
            if response.get("type") == "file":
                return [response["path"]]
            return []
        files: list[str] = []
        for item in response:
            if item.get("type") == "file":
                files.append(item["path"])
            elif item.get("type") == "dir":
                files.extend(self.list_files(item["path"], branch_name))
        return files

    def _content_sha(self, rel_path: str, branch_name: str) -> str | None:
        try:
            response = self._request("GET", f"/contents/{rel_path}?ref={branch_name}")
            return response["sha"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    def write_files(
        self,
        branch_name: str,
        files: list[RepositoryFileWrite],
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> str:
        self.ensure_branch(branch_name, self.default_branch)
        base_commit_sha = self._get_ref_sha(branch_name)
        base_commit = self._request("GET", f"/git/commits/{base_commit_sha}")

        tree = []
        for file in files:
            blob = self._request(
                "POST",
                "/git/blobs",
                json={
                    "content": base64.b64encode(file.content).decode("utf-8"),
                    "encoding": "base64",
                },
            )
            tree.append({"path": file.rel_path, "mode": "100644", "type": "blob", "sha": blob["sha"]})

        new_tree = self._request(
            "POST",
            "/git/trees",
            json={"base_tree": base_commit["tree"]["sha"], "tree": tree},
        )
        commit = self._request(
            "POST",
            "/git/commits",
            json={
                "message": commit_message,
                "tree": new_tree["sha"],
                "parents": [base_commit_sha],
                "author": {"name": author_name, "email": author_email},
            },
        )
        self._request(
            "PATCH",
            f"/git/refs/heads/{branch_name}",
            json={"sha": commit["sha"], "force": False},
        )
        return commit["sha"]

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
            return self._get_ref_sha(branch_name)
        self.ensure_branch(branch_name, self.default_branch)
        base_commit_sha = self._get_ref_sha(branch_name)
        base_commit = self._request("GET", f"/git/commits/{base_commit_sha}")
        tree = [{"path": rel_path, "mode": "100644", "type": "blob", "sha": None} for rel_path in unique_paths]
        new_tree = self._request(
            "POST",
            "/git/trees",
            json={"base_tree": base_commit["tree"]["sha"], "tree": tree},
        )
        commit = self._request(
            "POST",
            "/git/commits",
            json={
                "message": commit_message,
                "tree": new_tree["sha"],
                "parents": [base_commit_sha],
                "author": {"name": author_name, "email": author_email},
            },
        )
        self._request(
            "PATCH",
            f"/git/refs/heads/{branch_name}",
            json={"sha": commit["sha"], "force": False},
        )
        return commit["sha"]

    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str) -> dict:
        return self._request(
            "POST",
            "/pulls",
            json={"title": title, "body": body, "head": head_branch, "base": base_branch},
        )

    def create_issue(self, title: str, body: str) -> dict:
        return self._request("POST", "/issues", json={"title": title, "body": body})
