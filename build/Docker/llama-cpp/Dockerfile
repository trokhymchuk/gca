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

# ---- model ------------------------------------------------------------------
# Download the concrete GGUF file (not the HF cache layout) so the heavy image
# loads it via a plain model_path with no Hugging Face access at runtime.
# Isolated in its own stage so the token stays out of the published layers.
FROM python:3.12-alpine3.23 AS model

# Defaults match llm-llama-cpp-config.yml; override with --build-arg if needed.
ARG MODEL_REPO_ID="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
ARG MODEL_FILENAME="*4_k_m.gguf"

RUN pip install --no-cache-dir huggingface-hub

# Download the matching file, then move it to a fixed path the config points at.
RUN --mount=type=secret,id=hf_token \
    HF_TOKEN=$(cat /run/secrets/hf_token 2>/dev/null || true) \
    hf download "${MODEL_REPO_ID}" --include "${MODEL_FILENAME}" --local-dir /download \
    && mkdir -p /models \
    && find /download -name '*.gguf' -exec mv {} /models/model.gguf \; \
    && rm -rf /download \
    && test -f /models/model.gguf

# ---- heavy ------------------------------------------------------------------
# Same as final, but with the GGUF baked in at /models/model.gguf and a config
# that loads it directly, so the image runs fully offline.
FROM final AS heavy

COPY --from=model /models/model.gguf /models/model.gguf
COPY llm-llama-cpp-heavy-config.yml /app/llm-llama-cpp-heavy-config.yml

# ---- heavy-test -------------------------------------------------------------
# Runs the integration suite against the baked model. Meant to run with
# `--network none` to prove the image needs no Hugging Face access at runtime.
FROM heavy AS heavy-test

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
ENV VIRTUAL_ENV=/app/.venv
RUN uv pip install pytest

COPY tests/ /app/tests/
COPY pyproject.toml /app/pyproject.toml

ENV GCA_LLM_CONFIG=llm-llama-cpp-heavy-config.yml

WORKDIR /app
CMD ["/app/.venv/bin/pytest", "-m", "integration", "-v", "tests/"]

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
