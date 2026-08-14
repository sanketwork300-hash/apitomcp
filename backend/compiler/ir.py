
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IRParameter:
    """
    Intermediate Representation of an API parameter.
    """

    name: str
    location: str
    required: bool = False
    description: str = ""
    schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "location": self.location,
            "required": self.required,
            "description": self.description,
            "schema": self.schema,
        }


@dataclass
class IRRequestBody:
    """
    Intermediate Representation of an API request body.
    """

    required: bool = False
    description: str = ""
    content: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "description": self.description,
            "content": self.content,
        }


@dataclass
class IRResponse:
    """
    Intermediate Representation of an API response.
    """

    status_code: str
    description: str = ""
    content: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code,
            "description": self.description,
            "content": self.content,
        }


@dataclass
class IREndpoint:
    """
    Intermediate Representation of one API endpoint.

    This is the main unit that eventually becomes an MCP tool.
    """

    operation_id: str
    name: str
    description: str
    method: str
    path: str

    parameters: list[IRParameter] = field(
        default_factory=list
    )

    request_body: IRRequestBody | None = None

    responses: list[IRResponse] = field(
        default_factory=list
    )

    security: list[dict[str, Any]] = field(
        default_factory=list
    )

    tags: list[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "name": self.name,
            "description": self.description,
            "method": self.method,
            "path": self.path,
            "parameters": [
                parameter.to_dict()
                for parameter in self.parameters
            ],
            "request_body": (
                self.request_body.to_dict()
                if self.request_body
                else None
            ),
            "responses": [
                response.to_dict()
                for response in self.responses
            ],
            "security": self.security,
            "tags": self.tags,
        }


@dataclass
class MCPIR:
    """
    Complete Intermediate Representation for an
    API-to-MCP compilation.

    Pipeline:

        OpenAPI
           ↓
        Normalized API
           ↓
        MCPIR
           ↓
        MCP Server Generator
    """

    title: str
    description: str
    api_version: str

    source_type: str = "github"
    source_owner: str | None = None
    source_repository: str | None = None
    source_branch: str | None = None
    source_path: str | None = None

    servers: list[str] = field(
        default_factory=list
    )

    security: list[dict[str, Any]] = field(
        default_factory=list
    )

    endpoints: list[IREndpoint] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the complete IR into a JSON-serializable
        dictionary.
        """

        return {
            "title": self.title,
            "description": self.description,
            "api_version": self.api_version,
            "source": {
                "type": self.source_type,
                "owner": self.source_owner,
                "repository": self.source_repository,
                "branch": self.source_branch,
                "path": self.source_path,
            },
            "servers": self.servers,
            "security": self.security,
            "endpoints": [
                endpoint.to_dict()
                for endpoint in self.endpoints
            ],
            "metadata": self.metadata,
        }


class IRBuilder:
    """
    Builds MCPIR from the normalized OpenAPI representation.
    """

    def build(
        self,
        normalized: dict[str, Any],
        source: dict[str, Any] | None = None,
    ) -> MCPIR:
        """
        Convert normalized API data into MCPIR.
        """

        if not isinstance(normalized, dict):
            raise ValueError(
                "Normalized API must be a dictionary"
            )

        source = source or {}

        endpoints = []

        for endpoint_data in normalized.get(
            "endpoints",
            [],
        ):
            endpoint = self._build_endpoint(
                endpoint_data
            )

            endpoints.append(endpoint)

        return MCPIR(
            title=normalized.get(
                "title",
                "API",
            ),
            description=normalized.get(
                "description",
                "",
            ),
            api_version=normalized.get(
                "api_version",
                "",
            ),
            source_type=source.get(
                "source_type",
                "github",
            ),
            source_owner=source.get(
                "owner"
            ),
            source_repository=source.get(
                "repository"
            ),
            source_branch=source.get(
                "branch"
            ),
            source_path=source.get(
                "path"
            ),
            servers=normalized.get(
                "servers",
                [],
            ),
            security=normalized.get(
                "security",
                [],
            ),
            endpoints=endpoints,
            metadata={
                "openapi_version": normalized.get(
                    "version"
                ),
                "endpoint_count": len(
                    endpoints
                ),
            },
        )

    def _build_endpoint(
        self,
        data: dict[str, Any],
    ) -> IREndpoint:
        """
        Convert one normalized endpoint into IREndpoint.
        """

        parameters = [
            self._build_parameter(parameter)
            for parameter in data.get(
                "parameters",
                [],
            )
        ]

        request_body = self._build_request_body(
            data.get("request_body")
        )

        responses = [
            self._build_response(
                status_code=status_code,
                response=response,
            )
            for status_code, response in data.get(
                "responses",
                {},
            ).items()
        ]

        return IREndpoint(
            operation_id=data.get(
                "operation_id",
                "",
            ),
            name=data.get(
                "name",
                data.get(
                    "operation_id",
                    "api_tool",
                ),
            ),
            description=data.get(
                "description",
                "",
            ),
            method=data.get(
                "method",
                "GET",
            ).upper(),
            path=data.get(
                "path",
                "/",
            ),
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            security=data.get(
                "security",
                [],
            ),
            tags=data.get(
                "tags",
                [],
            ),
        )

    @staticmethod
    def _build_parameter(
        data: dict[str, Any],
    ) -> IRParameter:
        return IRParameter(
            name=data.get(
                "name",
                "",
            ),
            location=data.get(
                "in",
                "query",
            ),
            required=bool(
                data.get(
                    "required",
                    False,
                )
            ),
            description=data.get(
                "description",
                "",
            ),
            schema=data.get(
                "schema",
                {},
            ),
        )

    @staticmethod
    def _build_request_body(
        data: dict[str, Any] | None,
    ) -> IRRequestBody | None:
        if not data:
            return None

        return IRRequestBody(
            required=bool(
                data.get(
                    "required",
                    False,
                )
            ),
            description=data.get(
                "description",
                "",
            ),
            content=data.get(
                "content",
                {},
            ),
        )

    @staticmethod
    def _build_response(
        status_code: str,
        response: dict[str, Any],
    ) -> IRResponse:
        return IRResponse(
            status_code=str(
                status_code
            ),
            description=response.get(
                "description",
                "",
            ),
            content=response.get(
                "content",
                {},
            ),
        )


def build_ir(
    normalized: dict[str, Any],
    source: dict[str, Any] | None = None,
) -> MCPIR:
    """
    Convenience function for building the IR.
    """

    return IRBuilder().build(
        normalized=normalized,
        source=source,
    )

