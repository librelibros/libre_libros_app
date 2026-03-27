from pathlib import Path

from app.config import get_settings
from app.models import RepositoryProvider, RepositorySource
from app.services.repository.github_api import GitHubRepositoryClient
from app.services.repository.local_git import LocalGitRepositoryClient


def repository_client_for(source: RepositorySource):
    settings = get_settings()
    if source.provider == RepositoryProvider.local:
        repo_path = Path(source.local_path) if source.local_path else settings.repos_root / source.slug
        return LocalGitRepositoryClient(repo_path=repo_path, default_branch=source.default_branch)
    if not (source.github_owner and source.github_repo and source.github_token):
        raise ValueError("GitHub repositories require owner, repo and token")
    return GitHubRepositoryClient(
        owner=source.github_owner,
        repo=source.github_repo,
        token=source.github_token,
        default_branch=source.default_branch,
    )

