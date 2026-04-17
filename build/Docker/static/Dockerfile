# ---- builder ----------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-alpine3.23 AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv sync --frozen --no-dev --no-cache --no-editable

# ---- final ------------------------------------------------------------------
FROM python:3.12-alpine3.23

RUN apk add --no-cache git
RUN git config --global --add safe.directory '*'

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

# ENTRYPOINT ["gca", "analyze"]
