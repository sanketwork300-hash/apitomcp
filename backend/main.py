
from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.github.oauth import router as github_oauth_router
from backend.sources.github_source import GitHubSource
from backend.normalization.openapi_parser import (
    OpenAPIParser,
    OpenAPIParseError,
)
from backend.normalization.normalizer import (
    OpenAPINormalizer,
)
from backend.compiler.ir import (
    IRBuilder,
)
from backend.compiler.openapi_to_mcp import (
    OpenAPIToMCPCompiler,
)
from backend.generator.generate import (
    MCPServerGenerator,
)

load_dotenv()


app = FastAPI(
    title="API-to-MCP",
    description=(
        "Translate OpenAPI specifications from GitHub "
        "repositories into MCP servers."
    ),
    version="0.1.0",
)


# ------------------------------------------------------------------
# OAuth
# ------------------------------------------------------------------

app.include_router(
    github_oauth_router
)


# ------------------------------------------------------------------
# Pipeline components
# ------------------------------------------------------------------

parser = OpenAPIParser()
normalizer = OpenAPINormalizer()
ir_builder = IRBuilder()
compiler = OpenAPIToMCPCompiler()
generator = MCPServerGenerator(
    output_dir="generated"
)


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------


class RepositoryRequest(BaseModel):
    """
    Request for loading an API specification from GitHub.
    """

    access_token: str = Field(
        ...,
        min_length=1,
    )

    owner: str = Field(
        ...,
        min_length=1,
    )

    repo: str = Field(
        ...,
        min_length=1,
    )

    branch: str | None = None

    path: str | None = None


class CompileRequest(RepositoryRequest):
    """
    Request for running the complete API-to-MCP pipeline.
    """

    server_name: str | None = None


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


@app.get(
    "/",
    tags=["System"],
)
async def root() -> dict[str, Any]:
    return {
        "name": "API-to-MCP",
        "version": "0.1.0",
        "status": "running",
    }


@app.get(
    "/health",
    tags=["System"],
)
async def health() -> dict[str, str]:
    return {
        "status": "healthy"
    }


# ------------------------------------------------------------------
# GitHub
# ------------------------------------------------------------------


@app.get(
    "/github/user",
    tags=["GitHub"],
)
async def github_user(
    access_token: str,
) -> dict[str, Any]:
    """
    Return the GitHub user associated with an OAuth token.
    """

    try:
        source = GitHubSource(
            access_token
        )

        return await source.get_user()

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@app.get(
    "/github/repositories",
    tags=["GitHub"],
)
async def github_repositories(
    access_token: str,
    page: int = 1,
    per_page: int = 30,
) -> dict[str, Any]:
    """
    List repositories available to the authenticated GitHub user.
    """

    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="page must be >= 1",
        )

    if per_page < 1 or per_page > 100:
        raise HTTPException(
            status_code=400,
            detail="per_page must be between 1 and 100",
        )

    try:
        source = GitHubSource(
            access_token
        )

        repositories = (
            await source.list_repositories(
                page=page,
                per_page=per_page,
            )
        )

        return {
            "repositories": repositories,
            "count": len(repositories),
            "page": page,
            "per_page": per_page,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


@app.post(
    "/github/spec",
    tags=["GitHub"],
)
async def github_spec(
    request: RepositoryRequest,
) -> dict[str, Any]:
    """
    Find and load an OpenAPI specification from GitHub.

    If `path` is omitted, the system automatically searches for:

        openapi.yaml
        openapi.yml
        openapi.json
        swagger.yaml
        swagger.yml
        swagger.json
    """

    try:
        source = GitHubSource(
            request.access_token
        )

        result = await source.get_source(
            owner=request.owner,
            repo=request.repo,
            branch=request.branch,
            path=request.path,
        )

        # Don't unnecessarily expose the raw specification
        # in this endpoint response.
        return {
            "owner": result["owner"],
            "repository": result["repository"],
            "branch": result["branch"],
            "path": result["path"],
            "filename": result["filename"],
            "content": result["content"],
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ------------------------------------------------------------------
# Normalization
# ------------------------------------------------------------------


@app.post(
    "/pipeline/normalize",
    tags=["Pipeline"],
)
async def normalize_repository(
    request: RepositoryRequest,
) -> dict[str, Any]:
    """
    Load an OpenAPI specification from GitHub and normalize it.
    """

    try:
        source = GitHubSource(
            request.access_token
        )

        source_data = await source.get_source(
            owner=request.owner,
            repo=request.repo,
            branch=request.branch,
            path=request.path,
        )

        document = parser.parse(
            content=source_data["content"],
            filename=source_data["filename"],
        )

        normalized = normalizer.normalize(
            document
        )

        return {
            "source": {
                "owner": source_data["owner"],
                "repository": source_data["repository"],
                "branch": source_data["branch"],
                "path": source_data["path"],
            },
            "normalized": normalized,
        }

    except OpenAPIParseError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ------------------------------------------------------------------
# Compilation
# ------------------------------------------------------------------


@app.post(
    "/pipeline/compile",
    tags=["Pipeline"],
)
async def compile_repository(
    request: CompileRequest,
) -> dict[str, Any]:
    """
    Run:

        GitHub
          ↓
        OpenAPI parser
          ↓
        Normalizer
          ↓
        IR
          ↓
        MCP compiler

    Returns the compiled MCP definition.
    """

    try:
        source = GitHubSource(
            request.access_token
        )

        source_data = await source.get_source(
            owner=request.owner,
            repo=request.repo,
            branch=request.branch,
            path=request.path,
        )

        document = parser.parse(
            content=source_data["content"],
            filename=source_data["filename"],
        )

        normalized = normalizer.normalize(
            document
        )

        ir = ir_builder.build(
            normalized=normalized,
            source={
                "source_type": "github",
                "owner": source_data["owner"],
                "repository": source_data["repository"],
                "branch": source_data["branch"],
                "path": source_data["path"],
            },
        )

        mcp_definition = compiler.compile(
            ir
        )

        return {
            "success": True,
            "mcp": mcp_definition,
        }

    except OpenAPIParseError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ------------------------------------------------------------------
# Generation
# ------------------------------------------------------------------


@app.post(
    "/pipeline/generate",
    tags=["Pipeline"],
)
async def generate_repository(
    request: CompileRequest,
) -> dict[str, Any]:
    """
    Run the complete pipeline through server generation:

        GitHub
          ↓
        OpenAPI
          ↓
        Normalize
          ↓
        IR
          ↓
        MCP
          ↓
        Generate server
    """

    try:
        source = GitHubSource(
            request.access_token
        )

        source_data = await source.get_source(
            owner=request.owner,
            repo=request.repo,
            branch=request.branch,
            path=request.path,
        )

        document = parser.parse(
            content=source_data["content"],
            filename=source_data["filename"],
        )

        normalized = normalizer.normalize(
            document
        )

        ir = ir_builder.build(
            normalized=normalized,
            source={
                "source_type": "github",
                "owner": source_data["owner"],
                "repository": source_data["repository"],
                "branch": source_data["branch"],
                "path": source_data["path"],
            },
        )

        mcp_definition = compiler.compile(
            ir
        )

        output_path = generator.generate(
            mcp_definition=mcp_definition,
            server_name=request.server_name,
        )

        return {
            "success": True,
            "server_name": mcp_definition[
                "server"
            ]["name"],
            "tool_count": len(
                mcp_definition.get(
                    "tools",
                    [],
                )
            ),
            "generated_path": str(
                output_path
            ),
            "files": [
                "server.py",
                "Dockerfile",
                "requirements.txt",
                "mcp.json",
            ],
        }

    except OpenAPIParseError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ------------------------------------------------------------------
# Local development entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    host = os.getenv(
        "HOST",
        "0.0.0.0",
    )

    port = int(
        os.getenv(
            "PORT",
            "3000",
        )
    )

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=True,
    )

