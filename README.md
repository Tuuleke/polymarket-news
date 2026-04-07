## Work in progress

# Polymarket News

AI-powered news platform that translates prediction market data into readable news articles.

**Author:** Gregor Harry Tuul (IABB63)
**Supervisor:** Rivo Lemmik
**Thesis:** "Tehisintellektil põhineva uudisteplatvormi arendamine ennustusturgude andmete kättesaadavuse parandamiseks"

---

## Stack

| Layer     | Technology          |
|-----------|---------------------|
| Frontend  | Next.js 15 (React)  |
| Backend   | FastAPI (Python)    |
| Database  | PostgreSQL 16       |
| Container | Docker / Compose    |

## Project structure

```
polymarket-news/
├── frontend/          # Next.js app (App Router, TypeScript, Tailwind)
│   └── src/
│       ├── app/       # Pages and layouts
│       ├── components/# Reusable UI components
│       ├── lib/       # API client and utilities
│       └── types/     # Shared TypeScript types
├── backend/           # FastAPI app
│   └── app/
│       ├── api/       # Route handlers
│       ├── core/      # Config and settings
│       ├── db/        # SQLAlchemy models and session
│       ├── schemas/   # Pydantic request/response schemas
│       └── services/  # Polymarket API client, LLM service
└── docker-compose.yml
```

## Getting started

```bash
# 1. Copy and fill in environment variables
cp .env.example .env

# 2. Start all services
docker compose up --build

# Frontend → http://localhost:3000
# Backend  → http://localhost:8000
# API docs → http://localhost:8000/docs
```

## Development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```
