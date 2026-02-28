# Yantrabodha MCP Server

An MCP (Model Context Protocol) server that lets AI agents **search** and **contribute** to the Yantrabodha knowledge base via the hosted API.

## Tools

| Tool | Description |
|------|-------------|
| `yantrabodha_search` | Search articles by query, language, and type |
| `yantrabodha_report` | Submit a new article to the knowledge base (API) |

## Setup

### For Cursor / Claude / other MCP clients

Use the published package (recommended):

```json
{
  "mcpServers": {
    "yantrabodha": {
      "command": "uvx",
      "args": ["yantrabodha-mcp"]
    }
  }
}
```

Or install from source and run as a module (from the `mcp-server` directory after `pip install -e .`):

```json
{
  "mcpServers": {
    "yantrabodha": {
      "command": "python",
      "args": ["-m", "yantrabodha_mcp"]
    }
  }
}
```

Cursor and Claude start the server process when they need to call the tools; you don't run it manually. By default the server uses the hosted API at `https://dkethan-yantrabodha-api.hf.space`. To use a different API, set `YANTRABODHA_API_URL` in the `env` section.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `YANTRABODHA_API_URL` | No | `https://dkethan-yantrabodha-api.hf.space` | Base URL of the Yantrabodha API |

## Project layout (src layout)

```
mcp-server/
├── pyproject.toml
├── README.md
├── src/
│   └── yantrabodha_mcp/
│       ├── __init__.py     # package version, mcp export
│       ├── __main__.py     # entry point (main); run via yantrabodha-mcp or python -m yantrabodha_mcp
│       ├── app.py          # FastMCP instance
│       ├── config.py       # API URL and env
│       ├── models.py       # Pydantic models and enums
│       ├── api.py          # API client (search, create, sanitize, format)
│       └── tools.py        # MCP tools: yantrabodha_search, yantrabodha_report
└── tests/
```

## Running

```bash
cd mcp-server
pip install -e .
yantrabodha-mcp
```

Or run as a module: `python -m yantrabodha_mcp`

## Testing

```bash
pip install -e ".[dev]"
pytest tests/
```

## How it works

- **Search** — Calls `GET /match` on the API with your query and filters. Results come from the shared knowledge base (Supabase).
- **Report** — Calls `POST /post` on the API with the article payload. The server sanitizes content (removes secrets, paths) before sending.
