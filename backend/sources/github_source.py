
from __future__ import annotations

from typing import Any

from backend.github.client import GitHubClient
from backend.github.repositories import GitHubRepositoryService


class GitHubSource:
    """
    Source adapter for loading API specifications from GitHub.

    This class acts as the boundary between the GitHub integration
    and the API-to-MCP pipeline.

    Flow:

        GitHub access token
                ↓
        GitHubClient
                ↓
        GitHubRepositoryService
                ↓
        GitHubSource
                ↓
        normalization/
    """

    def __init__(self, access_token: str):
        self.client = GitHubClient(access_token)
        self.repositories = GitHubRepositoryService(self.client)

    async def get_user(self) -> dict[str, Any]:
        """
        Return the authenticated GitHub user.
        """

        return await self.client.get_authenticated_user()

    async def list_repositories(
        self,
        page: int = 1,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Return repositories accessible to the authenticated user.
        """

        return await self.repositories.list_repositories(
            page=page,
            per_page=per_page,
        )

    async def get_repository(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any]:
        """
        Return repository metadata.
        """

        return await self.repositories.get_repository(
            owner=owner,
            repo=repo,
        )

    async def find_api_specs(
        self,
        owner: str,
        repo: str,
        branch: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find OpenAPI/Swagger specification files in a repository.
        """

        return await self.repositories.find_openapi_files(
            owner=owner,
            repo=repo,
            branch=branch,
        )

    async def load_api_spec(
        self,
        owner: str,
        repo: str,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """
        Locate and load the most likely API specification.

        The returned content is still raw YAML/JSON.
        Parsing and normalization happen in the normalization layer.
        """

        return await self.repositories.get_openapi_spec(
            owner=owner,
            repo=repo,
            branch=branch,
        )

    async def load_spec_from_path(
        self,
        owner: str,
        repo: str,
        path: str,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """
        Load a specific API specification file from a repository.

        This is useful when a repository contains multiple
        OpenAPI specifications and the user explicitly selects one.
        """

        content = await self.repositories.get_openapi_content(
            owner=owner,
            repo=repo,
            path=path,
            branch=branch,
        )

        repository = await self.repositories.get_repository(
            owner=owner,
            repo=repo,
        )

        return {
            "owner": owner,
            "repository": repo,
            "branch": branch or repository.get("default_branch", "main"),
            "path": path,
            "filename": path.rsplit("/", 1)[-1],
            "content": content,
        }

    async def get_source(
        self,
        owner: str,
        repo: str,
        branch: str | None = None,
        path: str | None = None,
    ) -> dict[str, Any]:
        """
        Generic source entry point.

        If `path` is supplied, that exact file is loaded.

        Otherwise, the source automatically discovers the
        OpenAPI/Swagger specification.
        """

        if path:
            return await self.load_spec_from_path(
                owner=owner,
                repo=repo,
                path=path,
                branch=branch,
            )

        return await self.load_api_spec(
            owner=owner,
            repo=repo,
            branch=branch,
        )
