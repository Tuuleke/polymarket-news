FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY src ./src
ENV PYTHONPATH=/app/src

CMD ["uvicorn", "pmnews.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
