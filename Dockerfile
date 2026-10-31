# API image. Dependencies are installed from uv.lock so the image matches local dev exactly.
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/data/raw && chown -R app:app /app/data
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/src ./src
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "pmnews.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
