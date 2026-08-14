
from __future__ import annotations

from typing import Any

from .client import GitHubClient


OPENAPI_FILENAMES = {
    "openapi.yaml",
    "openapi.yml",
    "openapi.json",
    "swagger.yaml",
    "swagger.yml",
    "swagger.json",
}


class GitHubRepositoryService:
    """
    Repository-level operations built on top of GitHubClient.

    This service is responsible for:
    - listing repositories
    - retrieving repository metadata
    - discovering OpenAPI/Swagger specifications
    - reading the OpenAPI specification
    """

    def __init__(self, client: GitHubClient):
        self.client = client

    async def list_repositories(
        self,
        page: int = 1,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """
        List repositories accessible to the authenticated user.
        """

        repositories = await self.client.list_repositories(
            page=page,
            per_page=per_page,
        )

        return [
            {
                "id": repo.get("id"),
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "owner": repo.get("owner", {}).get("login"),
                "private": repo.get("private", False),
                "default_branch": repo.get("default_branch"),
                "html_url": repo.get("html_url"),
                "description": repo.get("description"),
            }
            for repo in repositories
        ]

    async def get_repository(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any]:
        """
        Retrieve repository metadata.
        """

        return await self.client.get_repository(
            owner,
            repo,
        )

    async def find_openapi_files(
        self,
        owner: str,
        repo: str,
        branch: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search the repository tree for OpenAPI/Swagger specification files.

        Example matches:
            openapi.yaml
            openapi.yml
            openapi.json
            swagger.yaml
            swagger.json

        The search is case-insensitive.
        """

        repository = await self.client.get_repository(
            owner,
            repo,
        )

        branch_name = branch or repository.get("default_branch", "main")

        tree = await self.client.get_repository_tree(
            owner,
            repo,
            branch=branch_name,
            recursive=True,
        )

        if tree.get("truncated"):
            raise RuntimeError(
                "GitHub repository tree is too large and was truncated. "
                "Use a more targeted file search."
            )

        files = []

        for item in tree.get("tree", []):
            if item.get("type") != "blob":
                continue

            path = item.get("path", "")
            filename = path.rsplit("/", 1)[-1].lower()

            if filename in OPENAPI_FILENAMES:
                files.append(
                    {
                        "path": path,
                        "filename": filename,
                        "sha": item.get("sha"),
                        "size": item.get("size"),
                        "url": item.get("url"),
                        "branch": branch_name,
                    }
                )

        return files

    async def find_openapi_file(
        self,
        owner: str,
        repo: str,
        branch: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Find the most likely OpenAPI specification in a repository.

        Preference is given to:
            1. openapi.yaml
            2. openapi.yml
            3. openapi.json
            4. swagger.yaml
            5. swagger.yml
            6. swagger.json
        """

        files = await self.find_openapi_files(
            owner,
            repo,
            branch=branch,
        )

        if not files:
            return None

        priority = {
            "openapi.yaml": 0,
            "openapi.yml": 1,
            "openapi.json": 2,
            "swagger.yaml": 3,
            "swagger.yml": 4,
            "swagger.json": 5,
        }

        files.sort(
            key=lambda item: (
                priority.get(item["filename"], 100),
                item["path"],
            )
        )

        return files[0]

    async def get_openapi_content(
        self,
        owner: str,
        repo: str,
        path: str,
        branch: str | None = None,
    ) -> str:
        """
        Retrieve the raw contents of an OpenAPI specification.
        """

        return await self.client.get_raw_file(
            owner=owner,
            repo=repo,
            path=path,
            ref=branch,
        )

    async def get_openapi_spec(
        self,
        owner: str,
        repo: str,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """
        Find and retrieve an OpenAPI/Swagger specification.

        Returns metadata and raw specification content.

        The specification is intentionally returned as raw text here.
        Parsing and normalization belong to the normalization layer.
        """

        openapi_file = await self.find_openapi_file(
            owner,
            repo,
            branch=branch,
        )

        if not openapi_file:
            raise FileNotFoundError(
                f"No OpenAPI/Swagger specification found in "
                f"{owner}/{repo}"
            )

        content = await self.get_openapi_content(
            owner=owner,
            repo=repo,
            path=openapi_file["path"],
            branch=openapi_file["branch"],
        )

        return {
            "owner": owner,
            "repository": repo,
            "branch": openapi_file["branch"],
            "path": openapi_file["path"],
            "filename": openapi_file["filename"],
            "content": content,
        }

