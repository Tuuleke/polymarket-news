from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pmnews.db.database import get_db
from pmnews.db.models import Article
from pmnews.api.schemas.article import ArticleRead

router = APIRouter()


@router.get("/", response_model=list[ArticleRead])
async def get_articles(
    article_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Article).order_by(Article.created_at.desc()).offset(offset).limit(limit)
    if article_type:
        stmt = stmt.where(Article.article_type == article_type)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{article_id}", response_model=ArticleRead)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
