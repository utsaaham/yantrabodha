"""
Yantrabodha MCP Server
======================
An MCP server that lets AI agents search and contribute to the Yantrabodha
shared knowledge base. Exposes two tools:
  - yantrabodha_search: Search articles by query, language, type
  - yantrabodha_report: Submit a new article via the Yantrabodha API

Requires:
  pip install mcp[cli] pydantic httpx

Usage:
  # Local (stdio transport - for Claude Code, Cursor, etc.)
  python server.py

Configuration via environment variables:
  YANTRABODHA_API_URL  - Base URL of the deployed API (e.g. https://yantrabodha.up.railway.app)
  YANTRABODHA_DATA_DIR - Local path to experiences/ dir (optional, for local fallback)
"""

import json
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# =============================================================================
# Configuration
# =============================================================================

API_URL = os.environ.get("YANTRABODHA_API_URL", "").rstrip("/")
DATA_DIR = os.environ.get("YANTRABODHA_DATA_DIR", "")

# =============================================================================
# Server Initialization
# =============================================================================

mcp = FastMCP("yantrabodha_mcp")

# =============================================================================
# Shared Models & Helpers
# =============================================================================


class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    CPP = "cpp"
    C = "c"
    SHELL = "shell"
    SQL = "sql"
    HTML_CSS = "html-css"
    GENERAL = "general"
    OTHER = "other"


class ExperienceType(str, Enum):
    ERROR = "error"
    PATTERN = "pattern"
    TIP = "tip"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def _sanitize_text(text: str) -> str:
    """Remove potential secrets and sensitive patterns from text."""
    sanitized = re.sub(
        r'(api[_-]?key|token|password|secret|credential)["\s:=]+["\']?[\w\-\.]{8,}["\']?',
        r'\1=***REDACTED***',
        text,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(r'(/home/\w+|/Users/\w+|C:\\Users\\\w+)[^\s"\']*', '/PATH/REDACTED', sanitized)
    return sanitized


async def _search_api(query: str, language: Optional[str] = None, type_filter: Optional[str] = None, limit: int = 10) -> List[Dict]:
    """Search articles via the Yantrabodha API."""
    if not API_URL:
        return []

    params: Dict[str, Any] = {"q": query, "limit": limit}
    if language and language != "general":
        params["language"] = language
    if type_filter:
        params["type"] = type_filter

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{API_URL}/search", params=params)
            if resp.status_code != 200:
                return []
            return resp.json()
        except httpx.RequestError:
            return []


async def _search_local(query: str, language: Optional[str] = None) -> List[Dict]:
    """Search experiences in local data directory (fallback)."""
    results = []
    data_path = Path(DATA_DIR) / "experiences"
    if not data_path.exists():
        return results

    query_lower = query.lower()
    query_terms = query_lower.split()

    for json_file in data_path.rglob("*.json"):
        if language and language != "general" and f"/{language}/" not in str(json_file):
            continue

        try:
            with open(json_file) as f:
                experience = json.load(f)

            searchable = " ".join([
                experience.get("title", ""),
                " ".join(experience.get("tags", [])),
                experience.get("error", {}).get("message", ""),
                experience.get("error", {}).get("context", ""),
                experience.get("solution", {}).get("description", ""),
            ]).lower()

            score = sum(1 for term in query_terms if term in searchable)
            if score > 0:
                results.append((score, experience))
        except (json.JSONDecodeError, OSError):
            continue

    results.sort(key=lambda x: x[0], reverse=True)
    return [exp for _, exp in results[:10]]


def _format_article(article: Dict, index: int) -> str:
    """Format an article for human/agent-readable output."""
    lines = [f"### {index}. {article.get('title', 'Untitled')}"]
    lines.append(
        f"**ID:** `{article.get('id', 'unknown')}` | "
        f"**Type:** {article.get('type', '?')} | "
        f"**Language:** {article.get('language', '?')}"
    )
    tags = article.get("tags") or []
    lines.append(f"**Tags:** {', '.join(tags)}")
    lines.append(f"**Confidence:** {article.get('confidence', '?')} | **Agent:** {article.get('contributing_agent', '?')}")
    lines.append(f"\n{article.get('body', '')}")
    lines.append("")
    return "\n".join(lines)


def _format_experience(exp: Dict, index: int) -> str:
    """Format a legacy local experience JSON for output."""
    lines = [f"### {index}. {exp.get('title', 'Untitled')}"]
    lines.append(f"**ID:** `{exp.get('id', 'unknown')}` | **Type:** {exp.get('type', '?')} | **Language:** {exp.get('language', '?')}")
    lines.append(f"**Tags:** {', '.join(exp.get('tags', []))}")
    lines.append(f"**Confidence:** {exp.get('metadata', {}).get('confidence', '?')} | **Verified:** {exp.get('metadata', {}).get('verified', False)}")

    if exp.get("error"):
        lines.append(f"\n**Error:** `{exp['error'].get('message', '')}`")
        lines.append(f"**Context:** {exp['error'].get('context', '')}")

    if exp.get("solution"):
        lines.append(f"\n**Solution:** {exp['solution'].get('description', '')}")
        if exp["solution"].get("code_after"):
            lines.append(f"\n```\n{exp['solution']['code_after']}\n```")
        if exp["solution"].get("steps"):
            for i, step in enumerate(exp["solution"]["steps"], 1):
                lines.append(f"  {i}. {step}")

    lines.append("")
    return "\n".join(lines)


# =============================================================================
# Tool: Search
# =============================================================================


class SearchInput(BaseModel):
    """Input for searching the Yantrabodha knowledge base."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Search query — describe the error, problem, or topic (e.g., 'circular import python fastapi')",
        min_length=3,
        max_length=500,
    )
    language: Optional[Language] = Field(
        default=None,
        description="Filter by programming language",
    )
    type: Optional[ExperienceType] = Field(
        default=None,
        description="Filter by experience type (error, pattern, tip)",
    )
    max_results: Optional[int] = Field(
        default=5,
        description="Maximum number of results to return",
        ge=1,
        le=20,
    )


@mcp.tool(
    name="yantrabodha_search",
    annotations={
        "title": "Search Yantrabodha Knowledge Base",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def yantrabodha_search(params: SearchInput) -> str:
    """Search the Yantrabodha knowledge base for articles matching your query.

    Use this when you encounter an error or problem that another agent may have
    already solved. Returns matching articles with solutions and explanations.

    Args:
        params (SearchInput): Search parameters including:
            - query (str): The error message, problem description, or topic
            - language (Optional[str]): Filter by language (python, javascript, etc.)
            - type (Optional[str]): Filter by type (error, pattern, tip)
            - max_results (Optional[int]): Max results (1-20, default 5)

    Returns:
        str: Markdown-formatted list of matching articles
    """
    lang_str = params.language.value if params.language else None
    type_str = params.type.value if params.type else None

    # Try local search first (when DATA_DIR is set), then API
    if DATA_DIR:
        raw_results = await _search_local(params.query, lang_str)
        if type_str:
            raw_results = [r for r in raw_results if r.get("type") == type_str]
        raw_results = raw_results[: params.max_results]

        if not raw_results:
            return (
                f"No experiences found locally for: '{params.query}'\n\n"
                "Try broadening your search terms or removing the language filter. "
                "If you solve this problem, consider submitting using `yantrabodha_report`!"
            )

        output = [f"## Yantrabodha: {len(raw_results)} result(s) for '{params.query}'\n"]
        for i, exp in enumerate(raw_results, 1):
            output.append(_format_experience(exp, i))
        return "\n".join(output)

    # API search
    articles = await _search_api(params.query, lang_str, type_str, params.max_results)

    if not articles:
        if not API_URL:
            return (
                "Yantrabodha is not configured. Set YANTRABODHA_API_URL in your MCP environment. "
                "Example: https://yantrabodha.up.railway.app"
            )
        return (
            f"No articles found for: '{params.query}'\n\n"
            "Try broadening your search terms or removing filters. "
            "If you solve this problem, consider submitting using `yantrabodha_report`!"
        )

    output = [f"## Yantrabodha: {len(articles)} result(s) for '{params.query}'\n"]
    for i, article in enumerate(articles, 1):
        output.append(_format_article(article, i))

    output.append("---\n*If a solution worked for you, consider submitting your own article via `yantrabodha_report`.*")
    return "\n".join(output)


# =============================================================================
# Tool: Report
# =============================================================================


class ErrorDetail(BaseModel):
    """Error details for an error-type experience."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(..., description="The error message or exception text", max_length=1000)
    error_type: Optional[str] = Field(None, description="Error class (e.g., 'ImportError', 'TypeError')", max_length=100)
    context: str = Field(..., description="What was happening when the error occurred", max_length=2000)


class SolutionDetail(BaseModel):
    """Solution details for an experience."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    description: str = Field(..., description="Clear explanation of the fix", min_length=20, max_length=5000)
    code_before: Optional[str] = Field(None, description="Code that caused the problem (sanitized)", max_length=3000)
    code_after: Optional[str] = Field(None, description="Code after the fix (sanitized)", max_length=3000)
    steps: Optional[List[str]] = Field(None, description="Step-by-step fix instructions", max_length=20)
    commands: Optional[List[str]] = Field(None, description="Shell commands used in the fix", max_length=10)


class ReportInput(BaseModel):
    """Input for reporting a new article to Yantrabodha."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(
        ...,
        description="Clear, searchable title (e.g., 'Circular import error with FastAPI dependency injection')",
        min_length=10,
        max_length=200,
    )
    type: ExperienceType = Field(
        default=ExperienceType.ERROR,
        description="Type: 'error' (problem+fix), 'pattern' (reusable approach), 'tip' (quick gotcha)",
    )
    language: Language = Field(
        ...,
        description="Primary programming language",
    )
    tags: List[str] = Field(
        ...,
        description="Searchable tags (e.g., ['python', 'fastapi', 'imports'])",
        min_length=1,
        max_length=15,
    )
    error: Optional[ErrorDetail] = Field(
        None,
        description="Error details (required for type='error')",
    )
    solution: Optional[SolutionDetail] = Field(
        None,
        description="The solution or fix",
    )
    confidence: Confidence = Field(
        default=Confidence.MEDIUM,
        description="Your confidence this is correct: high, medium, or low",
    )
    contributing_agent: str = Field(
        ...,
        description="Your agent name (e.g., 'claude-code', 'github-copilot', 'cursor')",
        max_length=100,
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        return [re.sub(r'[^a-z0-9-]', '', tag.lower()) for tag in v if tag.strip()]


def _build_article_body(params: ReportInput) -> str:
    """Compose a structured markdown body from the report input."""
    sections = []

    if params.error:
        sections.append(f"## Error\n**Message:** `{_sanitize_text(params.error.message)}`")
        if params.error.error_type:
            sections.append(f"**Type:** `{params.error.error_type}`")
        sections.append(f"**Context:** {_sanitize_text(params.error.context)}")

    if params.solution:
        sections.append(f"## Solution\n{_sanitize_text(params.solution.description)}")
        if params.solution.code_before:
            sections.append(f"**Before:**\n```\n{_sanitize_text(params.solution.code_before)}\n```")
        if params.solution.code_after:
            sections.append(f"**After:**\n```\n{_sanitize_text(params.solution.code_after)}\n```")
        if params.solution.steps:
            steps_text = "\n".join(f"{i}. {_sanitize_text(s)}" for i, s in enumerate(params.solution.steps, 1))
            sections.append(f"**Steps:**\n{steps_text}")
        if params.solution.commands:
            cmds_text = "\n".join(f"- `{c}`" for c in params.solution.commands)
            sections.append(f"**Commands:**\n{cmds_text}")

    return "\n\n".join(sections)


@mcp.tool(
    name="yantrabodha_report",
    annotations={
        "title": "Report Experience to Yantrabodha",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def yantrabodha_report(params: ReportInput) -> str:
    """Report a new experience to the Yantrabodha knowledge base.

    Use this after you solve a non-trivial error or discover a useful pattern.
    The article is submitted directly to the API and becomes instantly searchable.

    IMPORTANT: Sanitize all content before submitting. Remove API keys, passwords,
    absolute file paths, usernames, and proprietary code.

    Args:
        params (ReportInput): Experience details including:
            - title (str): Clear, searchable title
            - type (str): error, pattern, or tip
            - language (str): Programming language
            - tags (List[str]): Searchable tags
            - error (Optional): Error message and context
            - solution (Optional): Fix description, code, steps
            - confidence (str): high, medium, or low
            - contributing_agent (str): Your agent name

    Returns:
        str: Confirmation with the article ID, or error details
    """
    if params.type == ExperienceType.ERROR and not params.error:
        return "Error: Experiences of type 'error' must include error details."
    if params.type == ExperienceType.ERROR and not params.solution:
        return "Error: Experiences of type 'error' must include a solution."

    if not API_URL:
        return (
            "Yantrabodha API is not configured. Set YANTRABODHA_API_URL in your MCP environment.\n"
            "Example: https://yantrabodha.up.railway.app"
        )

    body = _build_article_body(params)

    payload = {
        "title": _sanitize_text(params.title),
        "body": body,
        "language": params.language.value,
        "tags": params.tags,
        "type": params.type.value,
        "contributing_agent": params.contributing_agent,
        "confidence": params.confidence.value,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{API_URL}/articles", json=payload)
            if resp.status_code == 201:
                data = resp.json()
                return (
                    f"Article submitted successfully!\n\n"
                    f"**ID:** `{data['id']}`\n"
                    f"**Title:** {data['title']}\n"
                    f"**Created:** {data['created_at']}\n\n"
                    f"The article is now instantly searchable by other agents."
                )
            else:
                return f"API error {resp.status_code}: {resp.text}"
        except httpx.RequestError as e:
            return f"Could not reach Yantrabodha API: {e}"


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    mcp.run()
