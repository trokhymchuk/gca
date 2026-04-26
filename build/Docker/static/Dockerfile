# ---- builder ----------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-alpine3.23 AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv sync --frozen --no-dev --no-cache --no-editable

# ---- final ------------------------------------------------------------------
FROM python:3.12-alpine3.23 AS final

RUN apk add --no-cache git
RUN git config --global --add safe.directory '*'

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

# ENTRYPOINT ["gca", "analyze"]

# ---- test -------------------------------------------------------------------
FROM final AS test

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
ENV VIRTUAL_ENV=/app/.venv
RUN uv pip install pytest

COPY tests/ /app/tests/
COPY pyproject.toml /app/pyproject.toml

WORKDIR /app
CMD ["/app/.venv/bin/pytest", "-m", "integration", "-v", "tests/"]
