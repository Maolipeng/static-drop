ARG IMAGE_REGISTRY=
FROM ${IMAGE_REGISTRY}python:3.12-slim

ARG PYPI_INDEX_URL=https://pypi.org/simple

# Install uv from the configured Python package index.
RUN pip install "uv==0.11.28" --index-url "${PYPI_INDEX_URL}"

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN UV_INDEX_URL="${PYPI_INDEX_URL}" uv sync --frozen --no-dev --no-install-project

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
