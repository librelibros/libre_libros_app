from pathlib import Path

from app.config import get_settings
from app.models import RepositoryProvider, RepositorySource
from app.services.repository.github_api import GitHubRepositoryClient
from app.services.repository.gitlab_api import GitLabRepositoryClient
from app.services.repository.local_git import LocalGitRepositoryClient


def repository_client_for(source: RepositorySource):
    settings = get_settings()
    if source.provider == RepositoryProvider.local:
        repo_path = Path(source.local_path) if source.local_path else settings.repos_root / source.slug
        return LocalGitRepositoryClient(repo_path=repo_path, default_branch=source.default_branch)
    namespace = source.repository_namespace or source.github_owner
    repository_name = source.repository_name or source.github_repo
    service_token = source.service_token or source.github_token
    if source.provider == RepositoryProvider.gitlab:
        if not (source.provider_url and namespace and repository_name and service_token):
            raise ValueError("GitLab repositories require url, namespace, repository and token")
        return GitLabRepositoryClient(
            base_url=source.provider_url,
            namespace=namespace,
            repository_name=repository_name,
            token=service_token,
            default_branch=source.default_branch,
        )
    if not (namespace and repository_name and service_token):
        raise ValueError("GitHub repositories require namespace, repository and token")
    return GitHubRepositoryClient(
        owner=namespace,
        repo=repository_name,
        token=service_token,
        default_branch=source.default_branch,
        api_url=source.provider_url,
    )
