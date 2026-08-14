
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .dispatcher import (
    ToolDispatcher,
    ToolNotFoundError,
    ToolValidationError,
)


class ToolCallRequest(BaseModel):
    """
    Request body for invoking an MCP tool.
    """

    tool_name: str = Field(
        ...,
        min_length=1,
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict
    )


class MCPRuntimeServer:
    """
    Runtime server for the compiled API-to-MCP server.

    Responsibilities:
        - expose available MCP tools
        - accept tool calls
        - dispatch calls to the underlying API
        - expose health information

    This is the HTTP runtime around the generated MCP tool layer.
    """

    def __init__(
        self,
        mcp_definition: dict[str, Any],
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
    ):
        self.mcp_definition = mcp_definition

        resolved_base_url = (
            base_url
            or os.getenv("API_BASE_URL")
        )

        self.dispatcher = ToolDispatcher(
            mcp_definition=mcp_definition,
            base_url=resolved_base_url,
            default_headers=default_headers,
        )

        self.app = FastAPI(
            title=mcp_definition.get(
                "server",
                {},
            ).get(
                "title",
                "API MCP Server",
            ),
            description=mcp_definition.get(
                "server",
                {},
            ).get(
                "description",
                "",
            ),
            version=mcp_definition.get(
                "server",
                {},
            ).get(
                "api_version",
                "1.0.0",
            ),
        )

        self._register_routes()

    def _register_routes(
        self,
    ) -> None:
        """
        Register runtime HTTP routes.
        """

        @self.app.get(
            "/health",
            tags=["Runtime"],
        )
        async def health() -> dict[str, Any]:
            return {
                "status": "healthy",
                "server": self._server_name(),
                "tool_count": len(
                    self.dispatcher.list_tools()
                ),
            }

        @self.app.get(
            "/tools",
            tags=["MCP"],
        )
        async def list_tools() -> dict[str, Any]:
            """
            Return MCP tool definitions.
            """

            tools = []

            for tool in self.dispatcher.list_tools():
                tools.append(
                    {
                        "name": tool.get(
                            "name"
                        ),
                        "description": tool.get(
                            "description",
                            "",
                        ),
                        "input_schema": tool.get(
                            "input_schema",
                            {},
                        ),
                        "output_schema": tool.get(
                            "output_schema",
                            {},
                        ),
                    }
                )

            return {
                "tools": tools,
                "count": len(tools),
            }

        @self.app.post(
            "/tools/call",
            tags=["MCP"],
        )
        async def call_tool(
            request: ToolCallRequest,
        ) -> dict[str, Any]:
            """
            Invoke an MCP tool.
            """

            try:
                return await self.dispatcher.dispatch(
                    tool_name=request.tool_name,
                    arguments=request.arguments,
                )

            except ToolNotFoundError as exc:
                raise HTTPException(
                    status_code=404,
                    detail=str(exc),
                ) from exc

            except ToolValidationError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=str(exc),
                ) from exc

        @self.app.get(
            "/",
            tags=["Runtime"],
        )
        async def root() -> dict[str, Any]:
            return {
                "name": self._server_name(),
                "description": self._server_description(),
                "tools": len(
                    self.dispatcher.list_tools()
                ),
                "health": "/health",
                "tool_list": "/tools",
                "tool_call": "/tools/call",
            }

    def _server_name(self) -> str:
        return (
            self.mcp_definition.get(
                "server",
                {},
            ).get(
                "name",
                "api_mcp_server",
            )
        )

    def _server_description(self) -> str:
        return (
            self.mcp_definition.get(
                "server",
                {},
            ).get(
                "description",
                "",
            )
        )


def create_app(
    mcp_definition: dict[str, Any],
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
) -> FastAPI:
    """
    Create a FastAPI runtime application.
    """

    runtime = MCPRuntimeServer(
        mcp_definition=mcp_definition,
        base_url=base_url,
        default_headers=default_headers,
    )

    return runtime.app

