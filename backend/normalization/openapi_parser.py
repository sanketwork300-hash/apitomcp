from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


class OpenAPIParseError(ValueError):
    """Raised when an OpenAPI specification cannot be parsed."""


class OpenAPIParser:
    """
    Parser for OpenAPI specifications.

    Supports:
        - YAML
        - JSON

    The parser converts the raw specification into a Python dictionary.
    Normalization and MCP conversion are handled by later pipeline stages.
    """

    SUPPORTED_VERSIONS = {"2.0", "3.0", "3.1"}

    def parse(
        self,
        content: str,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Parse an OpenAPI/Swagger specification from raw text.

        Args:
            content: Raw YAML or JSON specification.
            filename: Optional filename used to determine the format.

        Returns:
            Parsed specification as a dictionary.

        Raises:
            OpenAPIParseError: If parsing or validation fails.
        """

        if not content or not content.strip():
            raise OpenAPIParseError(
                "OpenAPI specification is empty"
            )

        data = self._parse_content(
            content=content,
            filename=filename,
        )

        self._validate_document(data)

        return data

    def parse_file(
        self,
        path: str | Path,
    ) -> dict[str, Any]:
        """
        Parse an OpenAPI specification from a local file.
        """

        file_path = Path(path)

        if not file_path.exists():
            raise OpenAPIParseError(
                f"OpenAPI specification not found: {file_path}"
            )

        try:
            content = file_path.read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise OpenAPIParseError(
                f"Failed to read OpenAPI specification: {exc}"
            ) from exc

        return self.parse(
            content=content,
            filename=file_path.name,
        )

    def _parse_content(
        self,
        content: str,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Parse JSON or YAML content.
        """

        extension = ""

        if filename:
            extension = Path(filename).suffix.lower()

        # Prefer JSON parsing for .json files.
        if extension == ".json":
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise OpenAPIParseError(
                    f"Invalid JSON OpenAPI specification: {exc}"
                ) from exc

            return self._ensure_dictionary(data)

        # Prefer YAML parsing for YAML files.
        if extension in {".yaml", ".yml"}:
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as exc:
                raise OpenAPIParseError(
                    f"Invalid YAML OpenAPI specification: {exc}"
                ) from exc

            return self._ensure_dictionary(data)

        # Unknown extension:
        # Try JSON first, then YAML.
        try:
            data = json.loads(content)
            return self._ensure_dictionary(data)
        except json.JSONDecodeError:
            pass

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise OpenAPIParseError(
                "Unable to parse specification as JSON or YAML"
            ) from exc

        return self._ensure_dictionary(data)

    @staticmethod
    def _ensure_dictionary(
        data: Any,
    ) -> dict[str, Any]:
        """
        Ensure the parsed document is a JSON/YAML object.
        """

        if not isinstance(data, dict):
            raise OpenAPIParseError(
                "OpenAPI specification must contain "
                "a top-level object"
            )

        return data

    def _validate_document(
        self,
        document: dict[str, Any],
    ) -> None:
        """
        Perform basic OpenAPI/Swagger validation.

        This is intentionally lightweight. Full schema validation
        is not required at this stage.
        """

        if "swagger" in document:
            version = str(document["swagger"])

            if version != "2.0":
                raise OpenAPIParseError(
                    f"Unsupported Swagger version: {version}"
                )

            self._validate_swagger_2(document)
            return

        if "openapi" in document:
            version = str(document["openapi"])

            major_version = version.split(".", 1)[0]

            if major_version != "3":
                raise OpenAPIParseError(
                    f"Unsupported OpenAPI version: {version}"
                )

            self._validate_openapi_3(document)
            return

        raise OpenAPIParseError(
            "Invalid API specification: expected "
            "'openapi' or 'swagger' field"
        )

    @staticmethod
    def _validate_openapi_3(
        document: dict[str, Any],
    ) -> None:
        """
        Validate the minimum required OpenAPI 3 structure.
        """

        if not isinstance(document.get("info"), dict):
            raise OpenAPIParseError(
                "OpenAPI specification must contain an 'info' object"
            )

        if not isinstance(document.get("paths"), dict):
            raise OpenAPIParseError(
                "OpenAPI specification must contain a 'paths' object"
            )

        info = document["info"]

        if not info.get("title"):
            raise OpenAPIParseError(
                "OpenAPI 'info.title' is required"
            )

        if not info.get("version"):
            raise OpenAPIParseError(
                "OpenAPI 'info.version' is required"
            )

    @staticmethod
    def _validate_swagger_2(
        document: dict[str, Any],
    ) -> None:
        """
        Validate the minimum required Swagger 2.0 structure.
        """

        if not isinstance(document.get("info"), dict):
            raise OpenAPIParseError(
                "Swagger specification must contain an 'info' object"
            )

        if not isinstance(document.get("paths"), dict):
            raise OpenAPIParseError(
                "Swagger specification must contain a 'paths' object"
            )

        if not document["info"].get("title"):
            raise OpenAPIParseError(
                "Swagger 'info.title' is required"
            )

        if not document["info"].get("version"):
            raise OpenAPIParseError(
                "Swagger 'info.version' is required"
            )

    @staticmethod
    def detect_version(
        document: dict[str, Any],
    ) -> str:
        """
        Return the OpenAPI/Swagger version from a parsed document.
        """

        if "openapi" in document:
            return str(document["openapi"])

        if "swagger" in document:
            return str(document["swagger"])

        raise OpenAPIParseError(
            "Unable to determine API specification version"
        )

    @staticmethod
    def is_openapi_3(
        document: dict[str, Any],
    ) -> bool:
        """
        Return True when the specification uses OpenAPI 3.x.
        """

        return "openapi" in document

    @staticmethod
    def is_swagger_2(
        document: dict[str, Any],
    ) -> bool:
        """
        Return True when the specification uses Swagger 2.0.
        """

        return document.get("swagger") == "2.0"