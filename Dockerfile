# syntax=docker/dockerfile:1

FROM python:3.14-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14-slim-trixie AS runtime

# Runtime dependencies come from the builder's virtual environment.
RUN python -m pip uninstall --yes --root-user-action=ignore pip

RUN apt-get update \
    && apt-get upgrade --no-install-recommends -y \
    && apt-get install --no-install-recommends -y tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 document-platform \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /app document-platform \
    && mkdir -p /app/data \
    && chown -R 10001:10001 /app

WORKDIR /app
COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 migrations ./migrations

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCUMENT_PLATFORM_STORAGE_ROOT=/app/data

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "document_platform.bootstrap:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
