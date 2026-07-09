FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY app ./app

# Create data directory
RUN mkdir -p /data/deployments /data/tmp /data/db

ENV DATA_DIR=/data
ENV DEPLOYMENTS_DIR=/data/deployments
ENV DB_PATH=/data/db/staticdrop.db
ENV TMP_DIR=/data/tmp

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
