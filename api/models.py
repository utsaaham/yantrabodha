"""Shared Pydantic models for the API."""
from typing import Optional

from pydantic import BaseModel


class ArticleIn(BaseModel):
    title: str
    body: str
    language: str = "general"
    tags: list[str] = []
    type: str = "error"
    contributing_agent: Optional[str] = None
    confidence: str = "medium"


class ArticleOut(BaseModel):
    id: str
    title: str
    created_at: str
