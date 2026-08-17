# API-to-MCP

Translate OpenAPI specifications from GitHub repositories into MCP (Model Context Protocol) servers.

## Overview

API-to-MCP is a compiler pipeline that:

1. **Fetches** OpenAPI/Swagger specs from GitHub repositories
2. **Normalizes** them into a canonical internal format
3. **Compiles** them to MCP tool definitions
4. **Generates** ready-to-deploy MCP server projects

## Requirements

- Python 3.11+
- GitHub OAuth App (for repository access)

### Python Dependencies

```bash
pip install -r requirements.txt
```

| Package | Purpose |
|---------|---------|
| fastapi | Web framework |
| uvicorn | ASGI server |
| httpx | HTTP client |
| pydantic | Data validation |
| PyYAML | YAML parsing |
| jinja2 | Template rendering |
| python-dotenv | Environment loading |

## Scope

### Supported Input
- OpenAPI 3.0 / 3.1 (YAML or JSON)
- Swagger 2.0 (YAML or JSON)
- Auto-discovery of spec files:
  - `openapi.yaml` / `openapi.yml` / `openapi.json`
  - `swagger.yaml` / `swagger.yml` / `swagger.json`

### Pipeline Stages

| Stage | Endpoint | Description |
|-------|----------|-------------|
| Fetch | `POST /github/spec` | Load spec from GitHub |
| Normalize | `POST /pipeline/normalize` | Parse + normalize spec |
| Compile | `POST /pipeline/compile` | Full pipeline to MCP definition |
| Generate | `POST /pipeline/generate` | Generate deployable server |

### Generated Output
```
generated/<server_name>/
├── server.py          # MCP server implementation
├── Dockerfile         # Container image
├── requirements.txt   # Runtime dependencies
└── mcp.json           # Compiled MCP definition (metadata)
```

## Configuration

Create a `.env` file:

```env
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_APP_ID=your_app_id
GITHUB_REDIRECT_URI=http://localhost:8001/auth/github/callback
```

## Execution

### Development Server

```bash
cd backend
python main.py
```

Server runs at `http://localhost:8001` with auto-reload.

### Docker

```bash
docker build -t api-to-mcp .
docker run -p 8001:8001 --env-file .env api-to-mcp
```

### API Usage

1. **Authenticate** via GitHub OAuth:
   ```
   GET /auth/github/login
   ```

2. **List repositories**:
   ```
   GET /github/repositories?access_token=<token>
   ```

3. **Generate MCP server**:
   ```
   POST /pipeline/generate
   {
     "access_token": "<token>",
     "owner": "org",
     "repo": "api-repo",
     "branch": "main",
     "server_name": "my-api-server"
   }
   ```

4. **Run generated server**:
   ```bash
   cd generated/my-api-server
   pip install -r requirements.txt
   python server.py
   ```

## Endpoints

| Method | Path | Tags |
|--------|------|------|
| GET | `/` | System |
| GET | `/health` | System |
| GET | `/auth/github/login` | GitHub |
| GET | `/auth/github/callback` | GitHub |
| GET | `/github/user` | GitHub |
| GET | `/github/repositories` | GitHub |
| POST | `/github/spec` | GitHub |
| POST | `/pipeline/normalize` | Pipeline |
| POST | `/pipeline/compile` | Pipeline |
| POST | `/pipeline/generate` | Pipeline |

## License

MIT