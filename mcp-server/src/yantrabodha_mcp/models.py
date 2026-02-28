"""Pydantic models and enums for the Yantrabodha MCP server."""

import re
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, ConfigDict


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


class ArticleType(str, Enum):
    ERROR = "error"
    PATTERN = "pattern"
    TIP = "tip"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


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
    type: Optional[ArticleType] = Field(
        default=None,
        description="Filter by article type (error, pattern, tip)",
    )
    max_results: Optional[int] = Field(
        default=5,
        description="Maximum number of results to return",
        ge=1,
        le=20,
    )


class ErrorDetail(BaseModel):
    """Error details for an error-type article."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    message: str = Field(..., description="The error message or exception text", max_length=1000)
    error_type: Optional[str] = Field(None, description="Error class (e.g., 'ImportError', 'TypeError')", max_length=100)
    context: str = Field(..., description="What was happening when the error occurred", max_length=2000)


class SolutionDetail(BaseModel):
    """Solution details for an article."""
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
    type: ArticleType = Field(
        default=ArticleType.ERROR,
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