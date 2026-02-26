"""
Netlify function entry point.
Wraps the FastAPI app with Mangum so it runs as a Lambda-compatible handler.
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from mangum import Mangum
from pydantic import BaseModel
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI(title="Yantrabodha API", version="1.0.0")


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


@app.post("/articles", response_model=ArticleOut, status_code=201)
def create_article(article: ArticleIn):
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
    q: str = Query(..., min_length=1),
    language: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=50),
):
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
    return query.execute().data


handler = Mangum(app, lifespan="off")
