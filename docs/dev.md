# Developer Guide

## Project Structure

```
gca/
├── src/git_commit_analyzer/
│   ├── cli.py              # Click CLI entry points (analyze, download-model)
│   ├── models.py           # GitCommit, Trailer data classes
│   ├── parser.py           # git log parsing → GitCommit objects
│   ├── rules.py            # Rule, Ruleset, config loading
│   ├── config.py           # AppConfig, LlmConfig dataclasses
│   ├── checkers/           # One subpackage per checker category
│   │   ├── subject/
│   │   ├── description/
│   │   ├── trailer/
│   │   ├── files/
│   │   └── llm/
│   └── filters/            # One subpackage per filter category
│       ├── commit_type/
│       ├── subject/
│       └── files/
├── tests/
│   ├── checkers/
│   ├── filters/
│   ├── commits/            # JSON fixtures for integration tests
│   ├── test_llm_checker.py
│   ├── test_llm_integration.py
│   ├── test_parser.py
│   └── test_rules.py
├── build/Docker/
│   ├── static/             # No LLM
│   ├── llama-cpp/          # llama-cpp-python backend
│   └── transformers/       # HuggingFace Transformers backend
├── docs/
│   ├── usage.md
│   └── dev.md
├── pyproject.toml
└── uv.lock
```

---

## Local Setup

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/).

```sh
git clone <repo-url>
cd gca
uv sync          # installs project + dev group (includes both LLM backends)
```

The `dev` group includes `pytest`, `pytest-cov`, `ruff`, and both LLM dependency groups. For a lighter install without LLM dependencies:

```sh
uv sync --no-dev --group dev-no-llm
```

After syncing, activate the virtual environment to use commands directly:

```sh
source .venv/bin/activate
gca analyze .
pytest
```

---

## Running Tests

### Unit tests

```sh
# Run all unit tests
uv run pytest -m "not integration"

# Specific file or test
uv run pytest tests/test_rules.py
uv run pytest tests/test_rules.py -k "test_filter_skips_commit"

# With coverage
uv run pytest -m "not integration" --cov=git_commit_analyzer --cov-report=term-missing
```

### Integration tests — llama-cpp

Require the `llm-llama-cpp` group and a config file at the project root.

```sh
uv sync --group llm-llama-cpp

GCA_LLM_CONFIG=llm-llama-cpp-config.yml uv run pytest tests/test_llm_integration.py -v -m integration
```

The first run downloads the model from Hugging Face. Subsequent runs use the local cache.

### Integration tests — Transformers

Require the `llm-transformers` group and a local model directory.

```sh
uv sync --group llm-transformers

GCA_LLM_CONFIG=llm-transformers-config.yml uv run pytest tests/test_llm_integration.py -v -m integration
```

The `llm-transformers-config.yml` at the repo root points to `/opt/output_classifier_production` (the Docker path). Update `model_path` to your local model directory for local development.

---

## Docker-based Testing

Each Dockerfile has a `test` target that installs pytest and runs the test suite inside the container.

### Static image (unit tests)

```sh
docker build --target test -t gca-static-test -f build/Docker/static/Dockerfile .
docker run --rm gca-static-test
```

### llama-cpp integration tests

The model downloads at container runtime via `HF_TOKEN`.

```sh
docker build --target test -t gca-llama-cpp-test -f build/Docker/llama-cpp/Dockerfile .
docker run --rm -e HF_TOKEN=$HF_TOKEN gca-llama-cpp-test
```

### Transformers integration tests

The model is baked in during build (requires `HF_TOKEN` as a build secret).

```sh
docker build \
  --target test \
  -t gca-transformers-test \
  -f build/Docker/transformers/Dockerfile \
  --secret id=hf_token,env=HF_TOKEN \
  .
docker run --rm gca-transformers-test
```

---

## Linting

```sh
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Auto-fix
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

---

## Adding a New Checker

1. Create a file under `src/git_commit_analyzer/checkers/<category>/`.

2. Subclass `CommitChecker`, set the `name` class attribute, and implement `__call__`:

   ```python
   from git_commit_analyzer.checkers.base import CommitChecker, CheckResult
   from git_commit_analyzer.models import GitCommit

   class MyChecker(CommitChecker):
       name = "my_checker"

       def __init__(self, threshold: int, **kwargs):
           super().__init__(**kwargs)
           self.threshold = threshold

       def __call__(self, commit: GitCommit) -> CheckResult:
           ok = len(commit.subject) >= self.threshold
           return CheckResult(
               passed=ok,
               message=f"Subject too short (min {self.threshold})" if not ok else "",
           )
   ```

3. Import the class in the category's `__init__.py` so it registers automatically.

4. Add the parameter mapping in `rules.py` where checker configs are parsed.

## Adding a New Filter

Same pattern as checkers, but subclass `CommitFilter` and return `bool`:

```python
from git_commit_analyzer.filters.base import CommitFilter
from git_commit_analyzer.models import GitCommit

class MyFilter(CommitFilter):
    name = "my_filter"

    def __call__(self, commit: GitCommit) -> bool:
        return not commit.is_merge
```

---

## Dependency Groups

| Group | Contents |
|---|---|
| `dev-no-llm` | `pytest`, `pytest-cov`, `ruff`. Used in the unit-test CI job. No LLM dependencies. |
| `llm-llama-cpp` | `llama-cpp-python`, `huggingface-hub`. |
| `llm-transformers` | `transformers`, `torch` (CPU build from the PyTorch index). |
| `dev` | Includes all of the above. Used for local full-stack development. |

```sh
# Just unit tests and linting
uv sync --no-dev --group dev-no-llm

# Unit tests + llama-cpp integration tests
uv sync --no-dev --group dev-no-llm --group llm-llama-cpp

# Everything
uv sync
```
