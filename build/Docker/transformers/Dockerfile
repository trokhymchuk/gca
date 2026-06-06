# ---- builder ----------------------------------------------------------------
# PyTorch does not ship musl/Alpine wheels — use glibc-based slim image.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ARG UV_EXTRA=llm-transformers

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv sync --frozen --no-dev --no-cache --no-editable --extra "${UV_EXTRA}"

# ---- model ------------------------------------------------------------------
# Download the private model in a separate stage. Consumed only by the `test`
# stage below — the published `final` image ships without the model. The HF
# token is mounted as a build secret so it never lands in a layer.
FROM python:3.12-slim-bookworm AS model

ARG MODEL_ID=trokhymchuk/commit-quality-model

RUN pip install --no-cache-dir huggingface-hub

RUN --mount=type=secret,id=hf_token \
    HF_TOKEN=$(cat /run/secrets/hf_token) \
    hf download "${MODEL_ID}" \
        --local-dir /opt/output_classifier_production

# ---- final ------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS final

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN git config --global --add safe.directory '*'

COPY --from=builder /app/.venv /app/.venv

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"

# ENTRYPOINT ["gca", "analyze"]

# ---- test -------------------------------------------------------------------
FROM final AS test

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=model /opt/output_classifier_production /opt/output_classifier_production
ENV VIRTUAL_ENV=/app/.venv
RUN uv pip install pytest

COPY tests/ /app/tests/
COPY pyproject.toml /app/pyproject.toml
COPY llm-transformers-config.yml /app/llm-transformers-config.yml

ENV GCA_LLM_CONFIG=llm-transformers-config.yml

WORKDIR /app
CMD ["/app/.venv/bin/pytest", "-m", "integration", "-v", "tests/"]
