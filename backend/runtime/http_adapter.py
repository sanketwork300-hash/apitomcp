
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx


class HTTPAdapterError(RuntimeError):
    """Raised when an HTTP API request fails."""


class HTTPAdapter:
    """
    Generic HTTP adapter used by the generated MCP runtime.

    Responsibilities:
        - Build API URLs
        - Substitute path parameters
        - Send query parameters
        - Send headers
        - Send request bodies
        - Handle API responses
        - Convert HTTP failures into structured errors

    The adapter does not know anything about OpenAPI or MCP.
    It only knows how to execute an HTTP request.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        default_headers: dict[str, str] | None = None,
    ):
        if not base_url:
            raise ValueError(
                "base_url is required"
            )

        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.default_headers = (
            default_headers or {}
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        body: Any = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute an HTTP request.

        Args:
            method:
                HTTP method such as GET, POST, PUT, DELETE.

            path:
                API path, e.g. /api/stock/{ticker}.

            path_params:
                Values used to replace {parameters} in the path.

            query_params:
                Query-string parameters.

            headers:
                Request-specific headers.

            body:
                JSON/request body.

            content_type:
                Optional Content-Type header.

        Returns:
            Structured response dictionary.
        """

        resolved_path = self._resolve_path(
            path,
            path_params or {},
        )

        url = urljoin(
            self.base_url,
            resolved_path.lstrip("/"),
        )

        request_headers = dict(
            self.default_headers
        )

        if headers:
            request_headers.update(
                {
                    str(key): str(value)
                    for key, value in headers.items()
                    if value is not None
                }
            )

        if content_type:
            request_headers.setdefault(
                "Content-Type",
                content_type,
            )

        # Don't send None-valued query parameters.
        params = {
            str(key): value
            for key, value in (
                query_params or {}
            ).items()
            if value is not None
        }

        request_kwargs: dict[str, Any] = {
            "method": method.upper(),
            "url": url,
            "params": params,
            "headers": request_headers,
        }

        if body is not None:
            request_kwargs["json"] = body

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.request(
                    **request_kwargs
                )

        except httpx.TimeoutException as exc:
            raise HTTPAdapterError(
                f"API request timed out: "
                f"{method.upper()} {url}"
            ) from exc

        except httpx.RequestError as exc:
            raise HTTPAdapterError(
                f"API request failed: "
                f"{method.upper()} {url}: {exc}"
            ) from exc

        return self._process_response(
            response
        )

    async def get(
        self,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a GET request."""

        return await self.request(
            "GET",
            path,
            **kwargs,
        )

    async def post(
        self,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a POST request."""

        return await self.request(
            "POST",
            path,
            **kwargs,
        )

    async def put(
        self,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a PUT request."""

        return await self.request(
            "PUT",
            path,
            **kwargs,
        )

    async def patch(
        self,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a PATCH request."""

        return await self.request(
            "PATCH",
            path,
            **kwargs,
        )

    async def delete(
        self,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a DELETE request."""

        return await self.request(
            "DELETE",
            path,
            **kwargs,
        )

    @staticmethod
    def _resolve_path(
        path: str,
        path_params: dict[str, Any],
    ) -> str:
        """
        Replace OpenAPI path parameters.

        Example:

            path:
                /api/stock/{ticker}

            path_params:
                {"ticker": "AAPL"}

            result:
                /api/stock/AAPL
        """

        resolved_path = path

        for name, value in path_params.items():
            placeholder = (
                "{"
                + str(name)
                + "}"
            )

            if placeholder not in resolved_path:
                continue

            resolved_path = resolved_path.replace(
                placeholder,
                str(value),
            )

        unresolved = []

        parts = resolved_path.split("/")

        for part in parts:
            if (
                part.startswith("{")
                and part.endswith("}")
            ):
                unresolved.append(part)

        if unresolved:
            raise HTTPAdapterError(
                "Missing path parameters: "
                + ", ".join(unresolved)
            )

        return resolved_path

    @staticmethod
    def _process_response(
        response: httpx.Response,
    ) -> dict[str, Any]:
        """
        Convert an HTTP response into a structured result.

        Successful example:

            {
                "success": True,
                "status_code": 200,
                "headers": {...},
                "data": {...}
            }

        Failed example:

            {
                "success": False,
                "status_code": 404,
                "headers": {...},
                "error": {...}
            }
        """

        response_headers = dict(
            response.headers
        )

        data = HTTPAdapter._parse_response_body(
            response
        )

        if 200 <= response.status_code < 300:
            return {
                "success": True,
                "status_code": response.status_code,
                "headers": response_headers,
                "data": data,
            }

        return {
            "success": False,
            "status_code": response.status_code,
            "headers": response_headers,
            "error": {
                "message": (
                    f"API returned HTTP "
                    f"{response.status_code}"
                ),
                "data": data,
            },
        }

    @staticmethod
    def _parse_response_body(
        response: httpx.Response,
    ) -> Any:
        """
        Parse JSON responses when possible.

        Falls back to plain text for non-JSON responses.
        """

        if not response.content:
            return None

        content_type = response.headers.get(
            "content-type",
            "",
        ).lower()

        if (
            "application/json" in content_type
            or "+json" in content_type
        ):
            try:
                return response.json()
            except ValueError:
                pass

        try:
            return response.text
        except Exception:
            return response.content

    def with_headers(
        self,
        headers: dict[str, str],
    ) -> HTTPAdapter:
        """
        Return a new adapter with additional default headers.

        Useful when the generated MCP server needs to attach
        API authentication such as:

            Authorization: Bearer <token>
            X-API-Key: <key>
        """

        merged_headers = dict(
            self.default_headers
        )

        merged_headers.update(
            headers
        )

        return HTTPAdapter(
            base_url=self.base_url,
            timeout=self.timeout,
            default_headers=merged_headers,
        )

