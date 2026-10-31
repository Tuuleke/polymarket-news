from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from pmnews.api.deps import MAX_PAGE_SIZE, DbSession
from pmnews.api.schemas.article import ArticleRead
from pmnews.db.models import Article

router = APIRouter()


@router.get("/", response_model=list[ArticleRead])
async def get_articles(
    db: DbSession,
    article_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Article]:
    stmt = select(Article).order_by(Article.created_at.desc()).offset(offset).limit(limit)
    if article_type:
        stmt = stmt.where(Article.article_type == article_type)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{article_id}", response_model=ArticleRead)
async def get_article(article_id: int, db: DbSession) -> Article:
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
