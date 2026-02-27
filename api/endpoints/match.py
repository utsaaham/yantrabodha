"""MATCH endpoint — full-text search across articles."""
from typing import Optional

from fastapi import APIRouter, Query

from database import supabase

router = APIRouter(tags=["match"])


@router.get("")
def match_articles(
    q: str = Query(..., min_length=1, description="Search query"),
    language: Optional[str] = Query(None, description="Filter by language"),
    type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(5, ge=1, le=50, description="Max results"),
):
    """Full-text search across article titles and bodies."""
    query = (
        supabase.table("articles")
        .select("id, title, body, language, tags, type, contributing_agent, confidence, created_at")
        .text_search("fts", q, config="english")
        .limit(limit)
    )
    if language:
        query = query.eq("language", language)
    if type:
        query = query.eq("type", type)
    result = query.execute()
    return result.data
