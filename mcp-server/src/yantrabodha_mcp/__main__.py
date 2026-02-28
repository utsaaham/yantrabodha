"""Entry point for running the MCP server."""

import sys

# Message to stderr so manual runs show progress; stdout is reserved for MCP protocol
print("Yantrabodha MCP loading...", file=sys.stderr)

from .app import mcp
from . import tools  # noqa: F401 — register tools with mcp


def main() -> None:
    print("Yantrabodha MCP server ready. Waiting for client (Ctrl+C to exit).", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
