# ---- builder ----------------------------------------------------------------
# Installs the package and its runtime dependencies into an isolated venv.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer — cached unless pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./

# Source layer — copied separately so the dependency cache is not invalidated
# by source-only edits.
COPY src/ src/

RUN uv sync --frozen --no-dev --no-cache --no-editable

# ---- final ------------------------------------------------------------------
# Minimal runtime image: git (required at runtime) + the pre-built venv only.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["git-commit-analyzer"]

