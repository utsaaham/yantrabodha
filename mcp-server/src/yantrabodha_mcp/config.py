"""Configuration for the Yantrabodha MCP server."""

import os

DEFAULT_API_URL = "https://dkethan-yantrabodha-api.hf.space"
API_URL = os.environ.get("YANTRABODHA_API_URL", DEFAULT_API_URL).rstrip("/")
