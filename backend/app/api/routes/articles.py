from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.article import ArticleRead

router = APIRouter()


@router.get("/", response_model=list[ArticleRead])
async def get_articles(
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    # TODO: implement
    raise NotImplementedError


@router.get("/{article_id}", response_model=ArticleRead)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    # TODO: implement
    raise NotImplementedError
