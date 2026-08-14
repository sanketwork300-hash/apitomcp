
import httpx
from typing import Any


GITHUB_API_URL = "https://api.github.com"


class GitHubClient:
    """
    Lightweight async client for interacting with the GitHub REST API.
    """

    def __init__(self, access_token: str):
        if not access_token:
            raise ValueError("GitHub access token is required")

        self.access_token = access_token

    @property
    def headers(self) -> dict[str, str]:
        """
        Headers required for authenticated GitHub API requests.
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> Any:
        """
        Execute an authenticated request against GitHub's API.
        """

        url = f"{GITHUB_API_URL}{endpoint}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                method,
                url,
                headers=self.headers,
                **kwargs,
            )

        if response.status_code >= 400:
            try:
                error = response.json()
            except Exception:
                error = response.text

            raise RuntimeError(
                f"GitHub API request failed "
                f"({response.status_code}): {error}"
            )

        if not response.content:
            return None

        return response.json()

    async def get_authenticated_user(self) -> dict[str, Any]:
        """
        Return information about the GitHub user associated
        with the access token.
        """
        return await self._request(
            "GET",
            "/user",
        )

    async def list_repositories(
        self,
        page: int = 1,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """
        List repositories accessible to the authenticated user.
        """

        return await self._request(
            "GET",
            "/user/repos",
            params={
                "page": page,
                "per_page": per_page,
                "sort": "updated",
                "direction": "desc",
            },
        )

    async def get_repository(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any]:
        """
        Get metadata for a specific repository.
        """

        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}",
        )

    async def get_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve a file or directory from a repository.

        GitHub's Contents API returns:
        - file metadata + base64 content for files
        - a list of entries for directories
        """

        params = {}

        if ref:
            params["ref"] = ref

        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            params=params,
        )

    async def get_repository_tree(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        recursive: bool = True,
    ) -> dict[str, Any]:
        """
        Retrieve the repository's Git tree.

        This is useful for discovering files such as:
        - openapi.yaml
        - openapi.yml
        - openapi.json
        - swagger.yaml
        - swagger.json
        """

        repository = await self.get_repository(
            owner,
            repo,
        )

        default_branch = repository.get(
            "default_branch",
            branch,
        )

        branch_name = branch or default_branch

        branch_data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/branches/{branch_name}",
        )

        commit_sha = branch_data["commit"]["sha"]

        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/git/trees/{commit_sha}",
            params={
                "recursive": "1" if recursive else "0",
            },
        )

    async def get_raw_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str | None = None,
    ) -> str:
        """
        Retrieve the raw text content of a repository file.
        """

        url = f"https://raw.githubusercontent.com/{owner}/{repo}"

        if ref:
            url = f"{url}/{ref}/{path}"
        else:
            repository = await self.get_repository(
                owner,
                repo,
            )

            default_branch = repository["default_branch"]

            url = f"{url}/{default_branch}/{path}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/vnd.github.raw+json",
                },
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Failed to fetch raw GitHub file "
                f"({response.status_code}): {response.text}"
            )

        return response.text

