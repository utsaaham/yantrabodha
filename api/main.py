"""
Yantrabodha Article API
=======================
FastAPI app backed by Supabase (Postgres). Endpoints:
  - POST /post   — submit a new article
  - GET  /match  — full-text search across articles

Environment variables:
  SUPABASE_URL         — from Supabase Project Settings → API
  SUPABASE_SERVICE_KEY — service role key (bypasses RLS)
"""

from fastapi import FastAPI

from database import supabase  # noqa: F401 — ensure DB is loaded
from endpoints.match import router as match_router
from endpoints.post import router as post_router

app = FastAPI(title="Yantrabodha API", version="1.0.0")

app.include_router(post_router, prefix="/post")
app.include_router(match_router, prefix="/match")
