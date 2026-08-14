
from __future__ import annotations

from typing import Any

from .ir import (
    IREndpoint,
    IRParameter,
    MCPIR,
)


class OpenAPIToMCPCompiler:
    """
    Converts the internal API IR into an MCP-oriented IR.

    The compiler does not generate Python source code directly.
    It converts API endpoints into MCP tool definitions that can
    later be consumed by the generator layer.

    Flow:

        OpenAPI
            ↓
        Normalizer
            ↓
        MCPIR
            ↓
        OpenAPIToMCPCompiler
            ↓
        MCP Tool IR
            ↓
        Generator
    """

    def compile(
        self,
        ir: MCPIR,
    ) -> dict[str, Any]:
        """
        Compile the complete API IR into an MCP server definition.
        """

        if not isinstance(ir, MCPIR):
            raise TypeError(
                "Expected MCPIR instance"
            )

        tools = []

        for endpoint in ir.endpoints:
            tools.append(
                self._compile_endpoint(endpoint)
            )

        return {
            "server": {
                "name": self._make_server_name(
                    ir.title
                ),
                "title": ir.title,
                "description": ir.description,
                "api_version": ir.api_version,
            },
            "source": {
                "type": ir.source_type,
                "owner": ir.source_owner,
                "repository": ir.source_repository,
                "branch": ir.source_branch,
                "path": ir.source_path,
            },
            "servers": ir.servers,
            "security": ir.security,
            "tools": tools,
            "metadata": {
                **ir.metadata,
                "tool_count": len(tools),
            },
        }

    def _compile_endpoint(
        self,
        endpoint: IREndpoint,
    ) -> dict[str, Any]:
        """
        Convert one API endpoint into an MCP tool.
        """

        input_schema = self._build_input_schema(
            endpoint
        )

        output_schema = self._build_output_schema(
            endpoint
        )

        return {
            "name": self._sanitize_tool_name(
                endpoint.name
            ),
            "operation_id": endpoint.operation_id,
            "description": endpoint.description,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "http": {
                "method": endpoint.method,
                "path": endpoint.path,
            },
            "parameters": [
                self._compile_parameter(parameter)
                for parameter in endpoint.parameters
            ],
            "request_body": self._compile_request_body(
                endpoint
            ),
            "responses": [
                response.to_dict()
                for response in endpoint.responses
            ],
            "security": endpoint.security,
            "tags": endpoint.tags,
        }

    def _build_input_schema(
        self,
        endpoint: IREndpoint,
    ) -> dict[str, Any]:
        """
        Build a JSON Schema representing all inputs required
        by the MCP tool.

        Path/query/header/cookie parameters become properties.

        Request body fields are represented under `body`.
        """

        properties: dict[str, Any] = {}
        required: list[str] = []

        for parameter in endpoint.parameters:
            property_schema = self._parameter_schema(
                parameter
            )

            properties[parameter.name] = property_schema

            if parameter.required:
                required.append(
                    parameter.name
                )

        if endpoint.request_body:
            body_schema = self._request_body_schema(
                endpoint
            )

            properties["body"] = body_schema

            if endpoint.request_body.required:
                required.append("body")

        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }

        if required:
            schema["required"] = required

        return schema

    def _parameter_schema(
        self,
        parameter: IRParameter,
    ) -> dict[str, Any]:
        """
        Convert an IR parameter schema into JSON Schema.

        Adds the parameter location as metadata so the runtime
        knows whether the value belongs in the path, query,
        headers, or cookies.
        """

        schema = dict(
            parameter.schema
            or {
                "type": "string"
            }
        )

        schema["x-parameter-location"] = (
            parameter.location
        )

        if parameter.description:
            schema.setdefault(
                "description",
                parameter.description,
            )

        return schema

    def _request_body_schema(
        self,
        endpoint: IREndpoint,
    ) -> dict[str, Any]:
        """
        Convert an API request body into JSON Schema.

        When multiple content types exist, they are represented
        using a oneOf structure.
        """

        request_body = endpoint.request_body

        if request_body is None:
            return {
                "type": "object"
            }

        content = request_body.content

        if not content:
            return {
                "type": "object"
            }

        schemas = []

        for content_type, schema in content.items():
            normalized_schema = self._normalize_schema(
                schema
            )

            normalized_schema[
                "x-content-type"
            ] = content_type

            schemas.append(
                normalized_schema
            )

        if len(schemas) == 1:
            return schemas[0]

        return {
            "oneOf": schemas,
            "description": (
                "Request body. Supported content types: "
                + ", ".join(content.keys())
            ),
        }

    def _build_output_schema(
        self,
        endpoint: IREndpoint,
    ) -> dict[str, Any]:
        """
        Build a JSON Schema for the successful API response.

        If multiple successful response schemas exist, they are
        represented using oneOf.
        """

        schemas = []

        for response in endpoint.responses:
            if not self._is_success_status(
                response.status_code
            ):
                continue

            for content_type, schema in response.content.items():
                normalized_schema = self._normalize_schema(
                    schema
                )

                normalized_schema[
                    "x-status-code"
                ] = response.status_code

                normalized_schema[
                    "x-content-type"
                ] = content_type

                schemas.append(
                    normalized_schema
                )

        if not schemas:
            return {
                "type": "object",
                "additionalProperties": True,
            }

        if len(schemas) == 1:
            return schemas[0]

        return {
            "oneOf": schemas
        }

    def _compile_parameter(
        self,
        parameter: IRParameter,
    ) -> dict[str, Any]:
        """
        Convert an IR parameter into an MCP parameter definition.
        """

        return {
            "name": parameter.name,
            "location": parameter.location,
            "required": parameter.required,
            "description": parameter.description,
            "schema": self._normalize_schema(
                parameter.schema
            ),
        }

    def _compile_request_body(
        self,
        endpoint: IREndpoint,
    ) -> dict[str, Any] | None:
        """
        Compile request body metadata for the runtime.
        """

        if endpoint.request_body is None:
            return None

        return {
            "required": endpoint.request_body.required,
            "description": endpoint.request_body.description,
            "content": endpoint.request_body.content,
            "content_types": list(
                endpoint.request_body.content.keys()
            ),
        }

    @staticmethod
    def _normalize_schema(
        schema: Any,
    ) -> dict[str, Any]:
        """
        Ensure a schema is represented as a dictionary.

        This is intentionally lightweight because schema
        normalization already happens upstream.
        """

        if isinstance(schema, dict):
            return dict(schema)

        if schema is None:
            return {
                "type": "object"
            }

        return {
            "type": "object",
            "x-original-schema": schema,
        }

    @staticmethod
    def _is_success_status(
        status_code: str,
    ) -> bool:
        """
        Return True for successful HTTP status codes.
        """

        status = str(status_code)

        if status.startswith("2"):
            return True

        # OpenAPI can use a default response, but it should not
        # automatically be treated as the successful response.
        return False

    @staticmethod
    def _sanitize_tool_name(
        name: str,
    ) -> str:
        """
        Make the tool name safe for MCP usage.
        """

        result = []

        for character in name:
            if character.isalnum() or character in (
                "_",
                "-",
            ):
                result.append(character)
            else:
                result.append("_")

        sanitized = "".join(result)

        while "__" in sanitized:
            sanitized = sanitized.replace(
                "__",
                "_",
            )

        sanitized = sanitized.strip(
            "_"
        )

        if not sanitized:
            sanitized = "api_tool"

        return sanitized[:128]

    @staticmethod
    def _make_server_name(
        title: str,
    ) -> str:
        """
        Generate a stable MCP server name from the API title.
        """

        result = []

        for character in title:
            if character.isalnum() or character in (
                "_",
                "-",
            ):
                result.append(
                    character.lower()
                )
            elif character.isspace():
                result.append("_")

        name = "".join(result)

        while "__" in name:
            name = name.replace(
                "__",
                "_",
            )

        name = name.strip(
            "_"
        )

        return name or "api_mcp_server"


def compile_to_mcp(
    ir: MCPIR,
) -> dict[str, Any]:
    """
    Convenience function for compiling MCPIR.
    """

    return OpenAPIToMCPCompiler().compile(ir)
