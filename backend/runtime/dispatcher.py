
from __future__ import annotations

from typing import Any

from .http_adapter import HTTPAdapter, HTTPAdapterError


class ToolNotFoundError(RuntimeError):
    """Raised when an MCP tool cannot be found."""


class ToolValidationError(RuntimeError):
    """Raised when MCP tool arguments are invalid."""


class ToolDispatcher:
    """
    Dispatches MCP tool calls to the underlying HTTP API.

    Flow:

        MCP tool call
              ↓
        ToolDispatcher
              ↓
        Resolve tool
              ↓
        Validate arguments
              ↓
        Split path/query/header/body
              ↓
        HTTPAdapter
              ↓
        API response
    """

    def __init__(
        self,
        mcp_definition: dict[str, Any],
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        if not isinstance(
            mcp_definition,
            dict,
        ):
            raise ValueError(
                "MCP definition must be a dictionary"
            )

        self.mcp_definition = mcp_definition

        self.tools = self._index_tools(
            mcp_definition.get(
                "tools",
                [],
            )
        )

        resolved_base_url = (
            base_url
            or self._get_default_base_url(
                mcp_definition
            )
        )

        if not resolved_base_url:
            raise ValueError(
                "No API base URL available. "
                "Provide base_url or define servers "
                "in the MCP definition."
            )

        self.http = HTTPAdapter(
            base_url=resolved_base_url,
            timeout=timeout,
            default_headers=default_headers,
        )

    async def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute an MCP tool call.

        Args:
            tool_name:
                Name of the MCP tool.

            arguments:
                Arguments supplied by the MCP client.

        Returns:
            Structured API response.
        """

        tool = self.get_tool(
            tool_name
        )

        arguments = arguments or {}

        self._validate_arguments(
            tool,
            arguments,
        )

        request = self._build_request(
            tool,
            arguments,
        )

        try:
            response = await self.http.request(
                method=request["method"],
                path=request["path"],
                path_params=request["path_params"],
                query_params=request["query_params"],
                headers=request["headers"],
                body=request["body"],
                content_type=request["content_type"],
            )

        except HTTPAdapterError as exc:
            return {
                "success": False,
                "error": {
                    "type": "http_adapter_error",
                    "message": str(exc),
                },
            }

        return self._format_tool_response(
            tool,
            response,
        )

    def get_tool(
        self,
        tool_name: str,
    ) -> dict[str, Any]:
        """
        Retrieve a compiled MCP tool by name.
        """

        tool = self.tools.get(
            tool_name
        )

        if tool is None:
            raise ToolNotFoundError(
                f"Unknown MCP tool: {tool_name}"
            )

        return tool

    def list_tools(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return all available MCP tools.
        """

        return list(
            self.tools.values()
        )

    def _build_request(
        self,
        tool: dict[str, Any],
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert MCP arguments into an HTTP request.

        Parameter locations are defined by the compiler:

            path
            query
            header
            cookie

        Request body is passed as `body`.
        """

        http_definition = tool.get(
            "http",
            {},
        )

        method = str(
            http_definition.get(
                "method",
                "GET",
            )
        ).upper()

        path = str(
            http_definition.get(
                "path",
                "/",
            )
        )

        path_params: dict[str, Any] = {}
        query_params: dict[str, Any] = {}
        headers: dict[str, Any] = {}
        cookies: dict[str, Any] = {}

        body = None
        content_type = None

        for parameter in tool.get(
            "parameters",
            [],
        ):
            if not isinstance(
                parameter,
                dict,
            ):
                continue

            name = parameter.get(
                "name"
            )

            if not name:
                continue

            if name not in arguments:
                continue

            value = arguments[name]

            location = str(
                parameter.get(
                    "location",
                    "query",
                )
            ).lower()

            if location == "path":
                path_params[name] = value

            elif location == "query":
                query_params[name] = value

            elif location == "header":
                headers[name] = value

            elif location == "cookie":
                cookies[name] = value

            elif location == "body":
                body = value

        # The compiler places the OpenAPI request body under
        # the `body` MCP argument.
        if "body" in arguments:
            body = arguments["body"]

        request_body = tool.get(
            "request_body"
        )

        if (
            body is not None
            and isinstance(
                request_body,
                dict,
            )
        ):
            content_types = request_body.get(
                "content_types",
                [],
            )

            if content_types:
                content_type = (
                    content_types[0]
                )

        if cookies:
            headers["Cookie"] = self._build_cookie_header(
                cookies
            )

        return {
            "method": method,
            "path": path,
            "path_params": path_params,
            "query_params": query_params,
            "headers": headers,
            "body": body,
            "content_type": content_type,
        }

    def _validate_arguments(
        self,
        tool: dict[str, Any],
        arguments: dict[str, Any],
    ) -> None:
        """
        Validate required MCP arguments.

        This performs basic validation only.

        Detailed JSON Schema validation can be added later
        using jsonschema or another validator.
        """

        input_schema = tool.get(
            "input_schema",
            {},
        )

        if not isinstance(
            input_schema,
            dict,
        ):
            return

        required = input_schema.get(
            "required",
            [],
        )

        if not isinstance(
            required,
            list,
        ):
            return

        missing = [
            name
            for name in required
            if name not in arguments
            or arguments[name] is None
        ]

        if missing:
            raise ToolValidationError(
                "Missing required arguments: "
                + ", ".join(
                    str(name)
                    for name in missing
                )
            )

    def _format_tool_response(
        self,
        tool: dict[str, Any],
        response: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Format the HTTP response as an MCP-friendly result.

        We preserve HTTP metadata because it is useful for
        debugging and for clients that need status information.
        """

        return {
            "tool": tool.get(
                "name"
            ),
            "success": response.get(
                "success",
                False,
            ),
            "status_code": response.get(
                "status_code"
            ),
            "data": response.get(
                "data"
            ),
            "error": response.get(
                "error"
            ),
            "headers": response.get(
                "headers",
                {},
            ),
        }

    @staticmethod
    def _index_tools(
        tools: Any,
    ) -> dict[str, dict[str, Any]]:
        """
        Index tools by name for fast lookup.
        """

        if not isinstance(
            tools,
            list,
        ):
            return {}

        indexed = {}

        for tool in tools:
            if not isinstance(
                tool,
                dict,
            ):
                continue

            name = tool.get(
                "name"
            )

            if not name:
                continue

            indexed[str(name)] = tool

        return indexed

    @staticmethod
    def _get_default_base_url(
        mcp_definition: dict[str, Any],
    ) -> str | None:
        """
        Select the first API server URL from the compiled definition.
        """

        servers = mcp_definition.get(
            "servers",
            [],
        )

        if not isinstance(
            servers,
            list,
        ):
            return None

        for server in servers:
            if isinstance(
                server,
                str,
            ) and server.strip():
                return server.rstrip("/")

        return None

    @staticmethod
    def _build_cookie_header(
        cookies: dict[str, Any],
    ) -> str:
        """
        Convert cookie values into a Cookie header.
        """

        return "; ".join(
            f"{name}={value}"
            for name, value in cookies.items()
        )


async def dispatch_tool(
    mcp_definition: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Convenience function for dispatching a single tool call.
    """

    dispatcher = ToolDispatcher(
        mcp_definition=mcp_definition,
        base_url=base_url,
        default_headers=default_headers,
    )

    return await dispatcher.dispatch(
        tool_name=tool_name,
        arguments=arguments,
    )

