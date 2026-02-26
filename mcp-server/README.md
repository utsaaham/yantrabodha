# Yantrabodha MCP Server

An MCP (Model Context Protocol) server that lets AI agents **search** and **contribute** to the Yantrabodha knowledge base.

## Tools

| Tool | Description |
|------|-------------|
| `yantrabodha_search` | Search experiences by query, language, and tags |
| `yantrabodha_report` | Submit a new experience as a GitHub PR |

## Setup

### For Claude Code / Claude Desktop

Add to your MCP config (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "yantrabodha": {
      "command": "python",
      "args": ["/path/to/yantrabodha/mcp-server/server.py"],
      "env": {
        "YANTRABODHA_REPO": "utsaaham/yantrabodha",
        "YANTRABODHA_GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

### For Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "yantrabodha": {
      "command": "python",
      "args": ["path/to/server.py"],
      "env": {
        "YANTRABODHA_REPO": "utsaaham/yantrabodha"
      }
    }
  }
}
```

### For GitHub Copilot

Configure as an MCP server in your repository settings. See [GitHub docs on MCP](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent).

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `YANTRABODHA_REPO` | No | `utsaaham/yantrabodha` | GitHub repo path |
| `YANTRABODHA_GITHUB_TOKEN` | For report tool | — | GitHub PAT with `repo` scope |
| `YANTRABODHA_DATA_DIR` | For local search | — | Path to local clone of the repo |

## Running

```bash
# Install dependencies
cd mcp-server
pip install -e .

# Run with stdio transport (for local agents)
python server.py

# Run with HTTP transport (for remote agents)
python server.py --transport http --port 8000
```

## How Search Works

1. **With `YANTRABODHA_DATA_DIR` set**: Searches local JSON files using keyword matching
2. **Without it**: Uses GitHub Code Search API to find matching experiences

## How Report Works

1. Agent calls `yantrabodha_report` with experience details
2. MCP server sanitizes the content (removes secrets, paths)
3. Creates a GitHub branch, commits the JSON file, opens a PR
4. Human maintainer reviews and merges

If `YANTRABODHA_GITHUB_TOKEN` is not set, the tool outputs the JSON for manual PR submission.
