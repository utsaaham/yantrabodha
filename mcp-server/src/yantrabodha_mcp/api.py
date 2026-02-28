"""API client and helpers for the Yantrabodha backend."""

import re
from typing import Optional, List, Dict, Any

import httpx

from .config import API_URL
from .models import ReportInput


def sanitize_text(text: str) -> str:
    """Remove potential secrets and sensitive patterns from text."""
    sanitized = re.sub(
        r'(api[_-]?key|token|password|secret|credential)["\s:=]+["\']?[\w\-\.]{8,}["\']?',
        r'\1=***REDACTED***',
        text,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(r'(/home/\w+|/Users/\w+|C:\\Users\\\w+)[^\s"\']*', '/PATH/REDACTED', sanitized)
    return sanitized


async def search_api(
    query: str,
    language: Optional[str] = None,
    type_filter: Optional[str] = None,
    limit: int = 10,
) -> List[Dict]:
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
            resp = await client.get(f"{API_URL}/match", params=params)
            if resp.status_code != 200:
                return []
            return resp.json()
        except httpx.RequestError:
            return []


def format_article(article: Dict, index: int) -> str:
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


def build_article_body(params: ReportInput) -> str:
    """Compose a structured markdown body from the report input."""
    sections = []

    if params.error:
        sections.append(f"## Error\n**Message:** `{sanitize_text(params.error.message)}`")
        if params.error.error_type:
            sections.append(f"**Type:** `{params.error.error_type}`")
        sections.append(f"**Context:** {sanitize_text(params.error.context)}")

    if params.solution:
        sections.append(f"## Solution\n{sanitize_text(params.solution.description)}")
        if params.solution.code_before:
            sections.append(f"**Before:**\n```\n{sanitize_text(params.solution.code_before)}\n```")
        if params.solution.code_after:
            sections.append(f"**After:**\n```\n{sanitize_text(params.solution.code_after)}\n```")
        if params.solution.steps:
            steps_text = "\n".join(f"{i}. {sanitize_text(s)}" for i, s in enumerate(params.solution.steps, 1))
            sections.append(f"**Steps:**\n{steps_text}")
        if params.solution.commands:
            cmds_text = "\n".join(f"- `{c}`" for c in params.solution.commands)
            sections.append(f"**Commands:**\n{cmds_text}")

    return "\n\n".join(sections)


async def create_article(payload: Dict[str, Any]) -> tuple[int, str | Dict]:
    """POST an article to the Yantrabodha API. Returns (status_code, body)."""
    if not API_URL:
        return 0, ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{API_URL}/post", json=payload)
            if resp.status_code == 201:
                return resp.status_code, resp.json()
            return resp.status_code, resp.text
        except httpx.RequestError as e:
            return 0, str(e)
