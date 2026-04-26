# ---- builder ----------------------------------------------------------------
# Compiles llama-cpp-python from source — requires C++ toolchain and cmake.
FROM ghcr.io/astral-sh/uv:python3.12-alpine3.23 AS builder

RUN apk add --no-cache \
    build-base \
    cmake \
    git \
    linux-headers \
    python3-dev \
    openssl-dev

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv sync --frozen --no-dev --no-cache --no-editable

# llama-cpp-python has no Alpine/musl wheel — compile from source.
RUN CMAKE_ARGS="-DLLAMA_MUSL=ON \
    -DGGML_AVX=OFF \
    -DGGML_AVX2=OFF \
    -DGGML_FMA=OFF \
    -DGGML_F16C=OFF \
    -DCMAKE_C_FLAGS='-mtune=generic' \
    -DCMAKE_CXX_FLAGS='-mtune=generic'" \
    uv sync --frozen --no-dev --no-cache --no-editable --extra llm-llama-cpp

# ---- final ------------------------------------------------------------------
FROM python:3.12-alpine3.23 AS final

RUN apk add --no-cache \
    git \
    libstdc++ \
    openblas \
    libgomp
RUN git config --global --add safe.directory '*'

COPY --from=builder /app/.venv /app/.venv

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"
ENV HF_HOME=/root/.cache/huggingface

# ENTRYPOINT ["gca", "analyze"]

# ---- test -------------------------------------------------------------------
FROM final AS test

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
ENV VIRTUAL_ENV=/app/.venv
RUN uv pip install pytest

COPY tests/ /app/tests/
COPY pyproject.toml /app/pyproject.toml
COPY llm-llama-cpp-config.yml /app/llm-llama-cpp-config.yml

ENV GCA_LLM_CONFIG=llm-llama-cpp-config.yml

WORKDIR /app
CMD ["/app/.venv/bin/pytest", "-m", "integration", "-v", "tests/"]
