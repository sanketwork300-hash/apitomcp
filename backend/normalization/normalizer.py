
from __future__ import annotations

from typing import Any


HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "trace",
}


class OpenAPINormalizer:
    """
    Converts a parsed OpenAPI/Swagger document into a common
    internal representation.

    The normalized representation is intentionally independent
    of OpenAPI version. The compiler layer can consume this
    representation without caring whether the source was
    OpenAPI 3.x or Swagger 2.0.
    """

    def normalize(
        self,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normalize an OpenAPI/Swagger document.

        Returns a structure containing:
            - API metadata
            - servers/base URL
            - normalized endpoints
        """

        if not isinstance(document, dict):
            raise ValueError(
                "OpenAPI document must be a dictionary"
            )

        version = self._detect_version(document)

        info = document.get("info", {})

        normalized = {
            "version": version,
            "title": info.get("title", "API"),
            "description": info.get("description", ""),
            "api_version": info.get("version", ""),
            "servers": self._extract_servers(document),
            "security": document.get("security", []),
            "endpoints": [],
        }

        paths = document.get("paths", {})

        if not isinstance(paths, dict):
            raise ValueError(
                "OpenAPI 'paths' must be an object"
            )

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                method_lower = method.lower()

                if method_lower not in HTTP_METHODS:
                    continue

                if not isinstance(operation, dict):
                    continue

                endpoint = self._normalize_endpoint(
                    document=document,
                    path=str(path),
                    method=method_lower,
                    operation=operation,
                    path_item=path_item,
                )

                normalized["endpoints"].append(endpoint)

        return normalized

    def _normalize_endpoint(
        self,
        document: dict[str, Any],
        path: str,
        method: str,
        operation: dict[str, Any],
        path_item: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert one OpenAPI operation into a normalized endpoint.
        """

        operation_id = operation.get("operationId")

        if not operation_id:
            operation_id = self._generate_operation_id(
                method=method,
                path=path,
            )

        parameters = []

        # Parameters defined at the path level.
        path_parameters = path_item.get(
            "parameters",
            [],
        )

        # Parameters defined at operation level.
        operation_parameters = operation.get(
            "parameters",
            [],
        )

        all_parameters = (
            path_parameters + operation_parameters
        )

        for parameter in all_parameters:
            if not isinstance(parameter, dict):
                continue

            resolved_parameter = self._resolve_reference(
                document,
                parameter,
            )

            normalized_parameter = self._normalize_parameter(
                document=document,
                parameter=resolved_parameter,
            )

            if normalized_parameter:
                parameters.append(normalized_parameter)

        request_body = self._normalize_request_body(
            document=document,
            operation=operation,
        )

        responses = self._normalize_responses(
            document=document,
            responses=operation.get(
                "responses",
                {},
            ),
        )

        return {
            "operation_id": operation_id,
            "name": self._make_tool_name(
                operation_id
            ),
            "description": operation.get(
                "description"
            )
            or operation.get(
                "summary"
            )
            or f"{method.upper()} {path}",
            "method": method.upper(),
            "path": path,
            "parameters": parameters,
            "request_body": request_body,
            "responses": responses,
            "security": operation.get(
                "security",
                document.get("security", []),
            ),
            "tags": operation.get(
                "tags",
                [],
            ),
        }

    def _normalize_parameter(
        self,
        document: dict[str, Any],
        parameter: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Normalize an OpenAPI parameter.
        """

        if not isinstance(parameter, dict):
            return None

        name = parameter.get("name")

        if not name:
            return None

        location = parameter.get(
            "in",
            "query",
        )

        schema = parameter.get(
            "schema",
        )

        # Swagger 2.0 parameters commonly define their type
        # directly instead of using a schema object.
        if schema is None:
            schema = {
                key: parameter[key]
                for key in (
                    "type",
                    "format",
                    "enum",
                    "default",
                    "minimum",
                    "maximum",
                    "minLength",
                    "maxLength",
                    "items",
                )
                if key in parameter
            }

        schema = self._resolve_schema(
            document,
            schema or {},
        )

        return {
            "name": name,
            "in": location,
            "required": bool(
                parameter.get(
                    "required",
                    False,
                )
            ),
            "description": parameter.get(
                "description",
                "",
            ),
            "schema": schema,
        }

    def _normalize_request_body(
        self,
        document: dict[str, Any],
        operation: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Normalize request body information.

        Handles:
            - OpenAPI 3 requestBody
            - Swagger 2 body parameters
        """

        request_body = operation.get(
            "requestBody"
        )

        if isinstance(request_body, dict):
            request_body = self._resolve_reference(
                document,
                request_body,
            )

            content = request_body.get(
                "content",
                {},
            )

            if not isinstance(content, dict):
                content = {}

            normalized_content = {}

            for content_type, media_type in content.items():
                if not isinstance(media_type, dict):
                    continue

                schema = media_type.get(
                    "schema",
                    {},
                )

                normalized_content[
                    content_type
                ] = self._resolve_schema(
                    document,
                    schema,
                )

            return {
                "required": bool(
                    request_body.get(
                        "required",
                        False,
                    )
                ),
                "description": request_body.get(
                    "description",
                    "",
                ),
                "content": normalized_content,
            }

        # Swagger 2.0
        for parameter in operation.get(
            "parameters",
            [],
        ):
            if not isinstance(parameter, dict):
                continue

            if parameter.get("in") != "body":
                continue

            schema = self._resolve_schema(
                document,
                parameter.get(
                    "schema",
                    {},
                ),
            )

            return {
                "required": bool(
                    parameter.get(
                        "required",
                        False,
                    )
                ),
                "description": parameter.get(
                    "description",
                    "",
                ),
                "content": {
                    "application/json": schema,
                },
            }

        return None

    def _normalize_responses(
        self,
        document: dict[str, Any],
        responses: Any,
    ) -> dict[str, Any]:
        """
        Normalize response schemas.
        """

        if not isinstance(responses, dict):
            return {}

        normalized = {}

        for status_code, response in responses.items():
            response = self._resolve_reference(
                document,
                response,
            )

            if not isinstance(response, dict):
                continue

            content = response.get(
                "content",
                {},
            )

            # Swagger 2.0 response format.
            if not content and response.get("schema"):
                content = {
                    "application/json": {
                        "schema": response.get(
                            "schema"
                        )
                    }
                }

            normalized_content = {}

            for content_type, media_type in content.items():
                if not isinstance(media_type, dict):
                    continue

                schema = media_type.get(
                    "schema",
                    {},
                )

                normalized_content[
                    content_type
                ] = self._resolve_schema(
                    document,
                    schema,
                )

            normalized[
                str(status_code)
            ] = {
                "description": response.get(
                    "description",
                    "",
                ),
                "content": normalized_content,
            }

        return normalized

    def _extract_servers(
        self,
        document: dict[str, Any],
    ) -> list[str]:
        """
        Extract API base URLs.

        OpenAPI 3:
            servers[].url

        Swagger 2:
            schemes + host + basePath
        """

        servers = document.get(
            "servers"
        )

        if isinstance(servers, list):
            result = []

            for server in servers:
                if not isinstance(server, dict):
                    continue

                url = server.get("url")

                if url:
                    result.append(str(url))

            if result:
                return result

        # Swagger 2.0 fallback.
        host = document.get("host")
        base_path = document.get(
            "basePath",
            "",
        )

        schemes = document.get(
            "schemes",
            ["https"],
        )

        if host:
            return [
                f"{scheme}://{host}{base_path}"
                for scheme in schemes
            ]

        return []

    def _resolve_reference(
        self,
        document: dict[str, Any],
        value: Any,
    ) -> Any:
        """
        Resolve a local JSON reference such as:

            #/components/schemas/User

        Only local references are resolved here.

        External references are left untouched.
        """

        if not isinstance(value, dict):
            return value

        reference = value.get(
            "$ref"
        )

        if not reference:
            return value

        if not reference.startswith("#/"):
            return value

        current: Any = document

        try:
            for part in reference[2:].split("/"):
                part = (
                    part.replace(
                        "~1",
                        "/",
                    )
                    .replace(
                        "~0",
                        "~",
                    )
                )

                current = current[part]

            return current

        except (
            KeyError,
            TypeError,
            IndexError,
        ):
            return value

    def _resolve_schema(
        self,
        document: dict[str, Any],
        schema: Any,
    ) -> Any:
        """
        Resolve a schema reference while preserving nested schemas.
        """

        if not isinstance(schema, dict):
            return schema

        resolved = self._resolve_reference(
            document,
            schema,
        )

        if resolved is not schema:
            return self._resolve_schema(
                document,
                resolved,
            )

        result = dict(schema)

        if "properties" in result:
            properties = result["properties"]

            if isinstance(properties, dict):
                result["properties"] = {
                    name: self._resolve_schema(
                        document,
                        property_schema,
                    )
                    for name, property_schema
                    in properties.items()
                }

        if "items" in result:
            result["items"] = self._resolve_schema(
                document,
                result["items"],
            )

        for key in (
            "allOf",
            "anyOf",
            "oneOf",
        ):
            if key not in result:
                continue

            values = result[key]

            if isinstance(values, list):
                result[key] = [
                    self._resolve_schema(
                        document,
                        item,
                    )
                    for item in values
                ]

        return result

    @staticmethod
    def _detect_version(
        document: dict[str, Any],
    ) -> str:
        """
        Detect OpenAPI/Swagger version.
        """

        if "openapi" in document:
            return str(
                document["openapi"]
            )

        if "swagger" in document:
            return str(
                document["swagger"]
            )

        raise ValueError(
            "Unable to determine OpenAPI/Swagger version"
        )

    @staticmethod
    def _generate_operation_id(
        method: str,
        path: str,
    ) -> str:
        """
        Generate a deterministic operation ID when
        the source specification does not provide one.

        Example:
            GET /api/stock/{ticker}

        becomes:

            get_api_stock_ticker
        """

        cleaned_path = path.strip("/")

        if not cleaned_path:
            cleaned_path = "root"

        result = []

        for character in cleaned_path:
            if character.isalnum():
                result.append(character)
            else:
                result.append("_")

        operation_id = (
            f"{method.lower()}_"
            f"{''.join(result)}"
        )

        while "__" in operation_id:
            operation_id = operation_id.replace(
                "__",
                "_",
            )

        return operation_id.strip("_")

    @staticmethod
    def _make_tool_name(
        operation_id: str,
    ) -> str:
        """
        Convert an operation ID into an MCP-safe tool name.
        """

        result = []

        for character in operation_id:
            if character.isalnum() or character in (
                "_",
                "-",
            ):
                result.append(character)
            else:
                result.append("_")

        name = "".join(result)

        while "__" in name:
            name = name.replace(
                "__",
                "_",
            )

        return name[:128]

