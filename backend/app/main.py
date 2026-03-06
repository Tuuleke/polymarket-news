from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered news platform for prediction market data",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers will be included here
# from app.api.routes import articles, markets
# app.include_router(articles.router, prefix="/api/v1/articles", tags=["articles"])
# app.include_router(markets.router, prefix="/api/v1/markets", tags=["markets"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
