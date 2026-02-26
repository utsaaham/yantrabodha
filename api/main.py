"""
Yantrabodha Article API
=======================
FastAPI app backed by Supabase (Postgres). Provides two endpoints:
  - POST /articles  — submit a new article
  - GET  /search    — full-text search across articles

Environment variables:
  SUPABASE_URL         — from Supabase Project Settings → API
  SUPABASE_SERVICE_KEY — service role key (bypasses RLS)
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from supabase import create_client, Client

# =============================================================================
# Supabase client
# =============================================================================

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# =============================================================================
# App
# =============================================================================

app = FastAPI(title="Yantrabodha API", version="1.0.0")


# =============================================================================
# Models
# =============================================================================


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


# =============================================================================
# Endpoints
# =============================================================================


@app.post("/articles", response_model=ArticleOut, status_code=201)
def create_article(article: ArticleIn):
    """Insert a new article into the knowledge base."""
    result = (
        supabase.table("articles")
        .insert(article.model_dump())
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to insert article")
    row = result.data[0]
    return ArticleOut(id=row["id"], title=row["title"], created_at=row["created_at"])


@app.get("/search")
def search_articles(
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
