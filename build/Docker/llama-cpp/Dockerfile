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
FROM python:3.12-alpine3.23

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
