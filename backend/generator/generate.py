from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class MCPServerGenerator:
    """
    Generates a complete MCP server project from the compiled
    MCP tool definition.

    Input:
        Output from OpenAPIToMCPCompiler.compile()

    Output:
        generated/
        └── <server_name>/
            ├── server.py
            ├── Dockerfile
            └── requirements.txt
    """

    def __init__(
        self,
        template_dir: str | Path | None = None,
        output_dir: str | Path = "generated",
    ):
        if template_dir is None:
            template_dir = (
                Path(__file__).resolve().parent / "templates"
            )

        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)

    def generate(
        self,
        mcp_definition: dict[str, Any],
        server_name: str | None = None,
    ) -> Path:
        """
        Generate an MCP server project.

        Args:
            mcp_definition:
                Compiled MCP definition returned by
                OpenAPIToMCPCompiler.

            server_name:
                Optional custom server name.

        Returns:
            Path to the generated server directory.
        """

        if not isinstance(mcp_definition, dict):
            raise ValueError(
                "MCP definition must be a dictionary"
            )

        server_info = mcp_definition.get(
            "server",
            {},
        )

        if server_name:
            name = server_name
        else:
            name = server_info.get(
                "name",
                "api_mcp_server",
            )

        name = self._sanitize_name(name)

        server_output_dir = (
            self.output_dir / name
        )

        server_output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._generate_server(
            mcp_definition=mcp_definition,
            output_dir=server_output_dir,
        )

        self._generate_dockerfile(
            mcp_definition=mcp_definition,
            output_dir=server_output_dir,
        )

        self._generate_requirements(
            mcp_definition=mcp_definition,
            output_dir=server_output_dir,
        )

        self._generate_metadata(
            mcp_definition=mcp_definition,
            output_dir=server_output_dir,
        )

        return server_output_dir

    def _generate_server(
        self,
        mcp_definition: dict[str, Any],
        output_dir: Path,
    ) -> None:
        """
        Render templates/server.py.
        """

        template_path = (
            self.template_dir / "server.py"
        )

        if not template_path.exists():
            raise FileNotFoundError(
                f"Server template not found: "
                f"{template_path}"
            )

        template = template_path.read_text(
            encoding="utf-8"
        )

        context = self._build_template_context(
            mcp_definition
        )

        rendered = self._render_template(
            template,
            context,
        )

        output_path = (
            output_dir / "server.py"
        )

        output_path.write_text(
            rendered,
            encoding="utf-8",
        )

    def _generate_dockerfile(
        self,
        mcp_definition: dict[str, Any],
        output_dir: Path,
    ) -> None:
        """
        Copy/render the Dockerfile template.
        """

        template_path = (
            self.template_dir / "Dockerfile"
        )

        if not template_path.exists():
            raise FileNotFoundError(
                f"Dockerfile template not found: "
                f"{template_path}"
            )

        template = template_path.read_text(
            encoding="utf-8"
        )

        context = self._build_template_context(
            mcp_definition
        )

        rendered = self._render_template(
            template,
            context,
        )

        output_path = (
            output_dir / "Dockerfile"
        )

        output_path.write_text(
            rendered,
            encoding="utf-8",
        )

    def _generate_requirements(
        self,
        mcp_definition: dict[str, Any],
        output_dir: Path,
    ) -> None:
        """
        Copy/render the requirements template.
        """

        template_path = (
            self.template_dir
            / "requirements.txt"
        )

        if not template_path.exists():
            raise FileNotFoundError(
                f"Requirements template not found: "
                f"{template_path}"
            )

        template = template_path.read_text(
            encoding="utf-8"
        )

        context = self._build_template_context(
            mcp_definition
        )

        rendered = self._render_template(
            template,
            context,
        )

        output_path = (
            output_dir / "requirements.txt"
        )

        output_path.write_text(
            rendered,
            encoding="utf-8",
        )

    def _generate_metadata(
        self,
        mcp_definition: dict[str, Any],
        output_dir: Path,
    ) -> None:
        """
        Store the compiled MCP definition alongside the
        generated server.

        This is useful for:
            - debugging
            - deployment
            - regeneration
            - inspecting generated tools
        """

        metadata_path = (
            output_dir / "mcp.json"
        )

        metadata_path.write_text(
            json.dumps(
                mcp_definition,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _build_template_context(
        self,
        mcp_definition: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build values available to the templates.
        """

        server = mcp_definition.get(
            "server",
            {},
        )

        source = mcp_definition.get(
            "source",
            {},
        )

        tools = mcp_definition.get(
            "tools",
            [],
        )

        servers = mcp_definition.get(
            "servers",
            [],
        )

        return {
            "server_name": server.get(
                "name",
                "api_mcp_server",
            ),
            "server_title": server.get(
                "title",
                "API MCP Server",
            ),
            "server_description": server.get(
                "description",
                "",
            ),
            "api_version": server.get(
                "api_version",
                "",
            ),
            "source_type": source.get(
                "type",
                "",
            ),
            "source_owner": source.get(
                "owner",
                "",
            ),
            "source_repository": source.get(
                "repository",
                "",
            ),
            "source_branch": source.get(
                "branch",
                "",
            ),
            "source_path": source.get(
                "path",
                "",
            ),
            "servers": servers,
            "tools": tools,
            "tool_count": len(tools),
            "tools_json": json.dumps(
                tools,
                indent=2,
            ),
            "mcp_definition_json": json.dumps(
                mcp_definition,
                indent=2,
            ),
        }

    @staticmethod
    def _render_template(
        template: str,
        context: dict[str, Any],
    ) -> str:
        """
        Very small template renderer.

        Supported syntax:

            {{server_name}}
            {{server_description}}

        Complex template logic should stay out of this layer.
        """

        rendered = template

        for key, value in context.items():
            placeholder = (
                "{{"
                + key
                + "}}"
            )

            if isinstance(value, (dict, list)):
                replacement = json.dumps(
                    value,
                    indent=2,
                )
            else:
                replacement = str(
                    value
                )

            rendered = rendered.replace(
                placeholder,
                replacement,
            )

        return rendered

    @staticmethod
    def _sanitize_name(
        name: str,
    ) -> str:
        """
        Convert a server name into a safe directory name.
        """

        name = str(name).strip().lower()

        name = re.sub(
            r"[^a-z0-9_-]+",
            "_",
            name,
        )

        name = re.sub(
            r"_+",
            "_",
            name,
        )

        name = name.strip(
            "_"
        )

        return name or "api_mcp_server"


def generate_server(
    mcp_definition: dict[str, Any],
    output_dir: str | Path = "generated",
    server_name: str | None = None,
) -> Path:
    """
    Convenience function for generating an MCP server.
    """

    generator = MCPServerGenerator(
        output_dir=output_dir
    )

    return generator.generate(
        mcp_definition=mcp_definition,
        server_name=server_name,
    )