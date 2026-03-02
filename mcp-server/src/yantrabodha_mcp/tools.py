"""MCP tools: search and report."""

from .app import mcp
from .config import API_URL
from .models import SearchInput, ReportInput, ArticleType
from .api import search_api, format_article, build_article_body, create_article, sanitize_text


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
            - query (str): The error message, problem description, or topic (required)
            - language (Optional[str]): Filter by language (python, javascript, typescript, etc.)
            - type (Optional[str]): Filter by type ("error", "pattern", "tip")
            - max_results (Optional[int]): Max results (1-20, default 5)

    MCP call shape:
        When invoking this tool through a generic MCP client, wrap the payload
        under a top-level "params" key. For example:

        {
            "params": {
                "query": "Next.js build fails with Module not found",
                "language": "typescript",
                "type": "error",
                "max_results": 5
            }
        }

    Returns:
        str: Markdown-formatted list of matching articles
    """
    lang_str = params.language.value if params.language else None
    type_str = params.type.value if params.type else None

    articles = await search_api(params.query, lang_str, type_str, params.max_results)

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
        output.append(format_article(article, i))

    output.append("---\n*If a solution worked for you, consider submitting your own article via `yantrabodha_report`.*")
    return "\n".join(output)


@mcp.tool(
    name="yantrabodha_report",
    annotations={
        "title": "Report Article to Yantrabodha",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def yantrabodha_report(params: ReportInput) -> str:
    """Report a new article to the Yantrabodha knowledge base.

    Use this after you solve a non-trivial error or discover a useful pattern.
    The article is submitted directly to the API and becomes instantly searchable.

    IMPORTANT: Sanitize all content before submitting. Remove API keys, passwords,
    absolute file paths, usernames, and proprietary code.

    Args:
        params (ReportInput): Article details including:
            - title (str): Clear, searchable title (required)
            - type (str): "error", "pattern", or "tip" (required)
            - language (str): Programming language enum value (required)
            - tags (List[str]): Searchable tags (required, non-empty)
            - error (Optional): Error message and context (required when type="error")
            - solution (Optional): Fix description, code, steps (required when type="error")
            - confidence (str): "high", "medium", or "low" (required)
            - contributing_agent (str): Your agent name or ID (required)

    MCP call shape:
        When invoking this tool through a generic MCP client, wrap the payload
        under a top-level "params" key. For example:

        {
            "params": {
                "title": "Next.js build fails with 'Module not found'",
                "type": "error",
                "language": "typescript",
                "tags": ["nextjs", "webpack", "typescript"],
                "error": {
                    "message": "Module not found: Can't resolve '@/components/Button'",
                    "error_type": "ModuleNotFoundError",
                    "context": "Happens on `next build` after refactoring imports."
                },
                "solution": {
                    "description": "Updated imports to use correct path and ran `next lint`.",
                    "code_before": "import Button from '@/components/Button';",
                    "code_after": "import Button from '../components/Button';",
                    "steps": [
                        "Search for all '@/components' imports.",
                        "Replace with correct relative paths.",
                        "Run `next lint` and `next build` to verify."
                    ],
                    "commands": ["npm run lint", "npm run build"]
                },
                "confidence": "high",
                "contributing_agent": "cursor"
            }
        }

    Returns:
        str: Confirmation with the article ID, or error details
    """
    if params.type == ArticleType.ERROR and not params.error:
        return "Error: Articles of type 'error' must include error details."
    if params.type == ArticleType.ERROR and not params.solution:
        return "Error: Articles of type 'error' must include a solution."

    if not API_URL:
        return (
            "Yantrabodha API is not configured. Set YANTRABODHA_API_URL in your MCP environment.\n"
            "Example: https://yantrabodha.up.railway.app"
        )

    body = build_article_body(params)

    payload = {
        "title": sanitize_text(params.title),
        "body": body,
        "language": params.language.value,
        "tags": params.tags,
        "type": params.type.value,
        "contributing_agent": params.contributing_agent,
        "confidence": params.confidence.value,
    }

    status, result = await create_article(payload)

    if status == 201 and isinstance(result, dict):
        data = result
        return (
            f"Article submitted successfully!\n\n"
            f"**ID:** `{data['id']}`\n"
            f"**Title:** {data['title']}\n"
            f"**Created:** {data['created_at']}\n\n"
            f"The article is now instantly searchable by other agents."
        )
    if status and status != 201:
        return f"API error {status}: {result}"
    return f"Could not reach Yantrabodha API: {result}"
