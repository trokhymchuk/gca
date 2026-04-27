# gca — Git Commit Analyzer

A CLI tool for validating git commit messages in CI pipelines. Define rules in a YAML config file: conventional commit format, length limits, required trailers, file-scope constraints, and optional LLM-based quality review.

## Installation

```sh
pip install gca

# With llama-cpp LLM support
pip install 'gca[llm-llama-cpp]'

# With Transformers LLM support
pip install 'gca[llm-transformers]'
```

Or with [uv](https://docs.astral.sh/uv/):

```sh
uv add gca
uv add 'gca[llm-llama-cpp]'
```

## Quick start

```sh
# Inspect HEAD commit
gca analyze .

# Analyze commits in a branch range
gca analyze . --base-ref main

# Validate against a rule config
gca analyze . --base-ref main --config rules.yml

# Analyze only the 10 most recent commits
gca analyze . --base-ref main --top-n 10

# GitLab CI
gca analyze . --base-ref $CI_MERGE_REQUEST_DIFF_BASE_SHA --config rules.yml

# GitHub Actions
gca analyze . --base-ref ${{ github.event.pull_request.base.sha }} --config rules.yml
```

Exit code is `0` when all rules pass, `1` (configurable) when any rule fails.

## Docker

```sh
# Static (no LLM)
docker run --rm -v "$(pwd):/repo" ghcr.io/trokhymchuk/gca-static /repo --base-ref main

# With llama-cpp LLM
docker run --rm -v "$(pwd):/repo" ghcr.io/trokhymchuk/gca-llm-llama-cpp /repo \
  --base-ref main --config /app/llm-llama-cpp-config.yml

# With Transformers LLM
docker run --rm -v "$(pwd):/repo" ghcr.io/trokhymchuk/gca-llm-transformers /repo \
  --base-ref main --config /app/llm-transformers-config.yml
```

## Documentation

- **[Usage guide](docs/usage.md)** — CLI reference, all filters and checkers with examples, LLM setup, CI integration
- **[Developer guide](docs/dev.md)** — local setup, running tests, Docker-based testing, project structure
