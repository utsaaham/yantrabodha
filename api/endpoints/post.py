"""POST endpoint — submit a new article."""
from fastapi import APIRouter, HTTPException

from database import supabase
from models import ArticleIn, ArticleOut

router = APIRouter(tags=["post"])


@router.post("", response_model=ArticleOut, status_code=201)
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
