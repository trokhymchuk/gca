# gca

A CLI tool for validating git commit messages in CI pipelines. Define rules in a YAML config file — conventional commit format, length limits, required trailers, file-scope constraints, and optional LLM-based quality review using a local GGUF model.

## Installation

```sh
pip install gca

# With LLM support (llama-cpp-python + huggingface-hub)
pip install 'gca[llm]'
```

Or with [uv](https://docs.astral.sh/uv/):

```sh
uv add gca
uv add 'gca[llm]'
```

---

## Running locally

Clone the repo and install in development mode:

```sh
git clone <repo-url>
cd gca
uv sync
```

With LLM support:

```sh
uv sync --extra llm
```

Run the CLI directly through uv:

```sh
# Inspect HEAD commit
uv run gca analyze .

# Inspect the last 3 commits
uv run gca analyze . --base-ref HEAD~3

# Run against rules
uv run gca analyze . --base-ref HEAD~3 --config example-config.yml
```

Or activate the virtualenv once and use the command directly:

```sh
source .venv/bin/activate
gca analyze . --base-ref HEAD~3 --config example-config.yml
```

> **Note:** Replace `HEAD~3` with your actual base branch (`main`, `master`, `origin/main`, etc.) when running in CI or against a full branch range.

---

## Commands

### `analyze`

Analyze commits in a repository against optional rules.

```
gca analyze [OPTIONS] [REPO_PATH]
```

| Option | Short | Default | Description |
|---|---|---|---|
| `--base-ref TEXT` | `-b` | — | Base ref for range (`main`, `origin/main`, `$CI_MERGE_REQUEST_DIFF_BASE_SHA`) |
| `--head-ref TEXT` | `-H` | `HEAD` | Head ref to analyze |
| `--format [text\|json]` | `-f` | `text` | Output format |
| `--no-merges` | | `false` | Exclude merge commits |
| `--config FILE` | `-c` | — | YAML config file. Repeatable — rules concatenated, configs merged (last wins) |

**Examples:**

```sh
# Inspect HEAD commit
gca analyze .

# Analyze all commits in a PR/MR range
gca analyze . --base-ref main
gca analyze . --base-ref origin/main --head-ref feature-branch

# GitLab CI
gca analyze . --base-ref $CI_MERGE_REQUEST_DIFF_BASE_SHA --format json

# With rules
gca analyze . --base-ref main --config rules.yml

# Layer multiple config files (org-wide base + project-specific)
gca analyze . --base-ref main --config base.yml --config project.yml
```

---

### `download-model`

Download a GGUF model from Hugging Face into the local cache. Requires the `[llm]` extra.

```
gca download-model [OPTIONS]
```

| Option | Short | Description |
|---|---|---|
| `--config FILE` | `-c` | YAML config file — reads `repo_id` and `filename` from `config.llm` |
| `--repo-id TEXT` | | Hugging Face repository ID |
| `--filename TEXT` | | Filename glob pattern, e.g. `'*q4_k_m.gguf'` |

**Examples:**

```sh
gca download-model --config llm-config.yml
gca download-model --repo-id Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF --filename '*q4_k_m.gguf'
```

---

## Config file

A YAML file with two top-level sections: `config:` (optional) and `rules:`.

```yaml
config:
  exit_code_on_failure: 1   # exit code when any rule fails (default: 1)
  debug: false              # print prompts and LLM responses to stderr

rules:
  - name: my-rule
    filters:                # optional — skip commits that don't match
      - type: <filter>
        ...
    checkers:               # required — what to enforce
      - type: <checker>
        ...
```

### Filters

Filters control which commits a rule applies to. All filters on a rule must pass for the commit to be checked. Add `invert: true` to negate any filter.

| Type | Parameters | Description |
|---|---|---|
| `commit_type` | `types: [...]` | Matches commits of the given types. Valid types: `fixup`, `squash`, `amend`, `merge`, `revert`, `regular`. |
| `paths_modified` | `any_of: [...]`, `all_of: [...]` | Matches based on which paths were modified. `any_of` — passes if at least one listed path matches a changed file. `all_of` — passes if every listed path has at least one match. Both can be combined (both must hold). Each entry can be an exact file path, a directory prefix ending with `/`, or a glob pattern (containing `*`, `?`, or `[`). At least one parameter must be provided. |
| `subject_prefix` | `any_of: [[...], ...]`, `all_of: [[...], ...]` | Matches based on the commit's prefix chain. Each inner list is an ordered chain of prefix tokens (e.g. `["ci", "cram"]` matches `ci: cram: …`). `any_of` — passes if the chain matches any pattern. `all_of` — passes if the chain matches all patterns. Accepts both conventional (`prefix(scope): `) and non-conventional (`prefix: `) formats. |

### Checkers

Checkers define what must be true about a commit that passed its filters. Add `invert: true` to negate any checker.

**Subject**

| Type | Parameters | Description |
|---|---|---|
| `subject_matches_regex` | `pattern: "..."` | Subject must match the regex |
| `subject_length` | `min: N`, `max: N` | Subject length must be within bounds (both optional, at least one required) |
| `subject_prefix` | `require_prefix: bool`, `conventional: bool`, `required: [[...], ...]`, `whitelist: [[...], ...]`, `blacklist: [[...], ...]`, `mode: whitelist\|blacklist` | Validates the commit subject prefix chain. `require_prefix` (default `true`) — fails if no prefix is found. `conventional` (default `false`) — requires `prefix(scope): …` format. `required` — list of chain patterns; the chain must match **at least one** (OR semantics). Each inner list is a contiguous subsequence match: `[["ci"], ["cram"]]` passes if the chain contains `ci` OR `cram`; `[["ci", "cram"]]` requires the chain to contain `ci: cram:` as a consecutive pair. Each `whitelist`/`blacklist` entry is an exact chain (e.g. `["ci", "cram"]` matches `ci: cram: …`). `whitelist` — if set, defaults to `whitelist` mode. `blacklist` — if set, defaults to `blacklist` mode. `mode` must be explicit when both are provided. |

**Description (body)**

| Type | Parameters | Description |
|---|---|---|
| `description_matches_regex` | `pattern: "..."` | Description must match the regex |
| `description_length` | `min: N`, `line_max: N` | Description must be at least N chars total and/or no line may exceed line_max chars (both optional, at least one required) |

**Trailers**

| Type | Parameters | Description |
|---|---|---|
| `trailer_present` | `required: [...]`, `at_least_one_of: [[...], ...]`, `exactly_one_of: [[...], ...]`, `whitelist: [...]`, `blacklist: [...]`, `mode: whitelist\|blacklist` | Flexible trailer validation. `required` — all must be present. `at_least_one_of` — for each group, at least one must be present. `exactly_one_of` — for each group, exactly one must be present. `whitelist` — additional allowed tokens (relevant in whitelist mode). `blacklist` — tokens that must not be present. `mode` defaults to `blacklist` (unlisted tokens are allowed); set to `whitelist` to reject any trailer not in the known sets. |

**Changed files**

| Type | Parameters | Description |
|---|---|---|
| `paths_modified` | `required: [...]`, `whitelist: [...]`, `blacklist: [...]`, `mode: whitelist\|blacklist` | `required` — these paths must be modified. `whitelist` — if set, defaults to `whitelist` mode (only listed paths may be modified). `blacklist` — if set, defaults to `blacklist` mode (listed paths are forbidden, others allowed). `mode` must be explicit when both are provided. Entries ending with `/` are directory prefixes; others are exact file paths. |
| `isolate_changes` | `groups: [[...], ...]` | Enforces that changes stay within defined isolation groups. Each inner list is a group of paths that belong together. If any changed file belongs to a group, ALL changed files must fit entirely within at least one single group. Files not in any group are freely allowed only when no group is triggered. Entries ending with `/` are directory prefixes; others are exact file paths. |

**LLM** *(requires `[llm]` extra)*

| Type | Parameters | Description |
|---|---|---|
| `llm` | `include_subject: bool`, `include_description: bool` | Review the commit with a local GGUF model. The model must respond with `PASS` or `FAIL` as the first word. |

---

## LLM checker

The `llm` checker runs a local GGUF model via [llama-cpp-python](https://github.com/abetlen/llama-cpp-python). No external API is required.

Add a `config.llm` section to your config file:

```yaml
config:
  llm:
    # Option A — download from Hugging Face on first use
    repo_id: "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
    filename: "*q4_k_m.gguf"

    # Option B — local file
    # model_path: "/models/model.gguf"

    context_window: 4096
    max_tokens: 60
    stop: ["<|im_end|>"]
    verbose: false

    prompt: |
      <|im_start|>system
      You are a senior software engineer reviewing git commit messages.
      Respond with PASS or FAIL as the very first word, followed by a one-sentence reason.

      PASS if ALL of the following are true:
        - Follows conventional-commits format: type(scope): description
        - Subject is specific and explains what changed
        - Description (if present) explains why the change was made

      FAIL if ANY of the following are true:
        - No conventional-commits prefix (feat/fix/chore/docs/etc.)
        - Subject is vague (e.g. "fix stuff", "update", "WIP")
        - Less than 10 meaningful characters in the subject
      <|im_end|>
      <|im_start|>user
      {commit}
      <|im_end|>
      <|im_start|>assistant

rules:
  - name: llm-commit-review
    filters:
      - type: commit_type
        types: ["merge"]
        invert: true
    checkers:
      - type: llm
        include_subject: true
        include_description: true
```

Pre-download the model before first use:

```sh
gca download-model --config llm-config.yml
```

---

## Example config

See [`example-config.yml`](example-config.yml) for a full reference covering every filter and checker type.

---

## Docker

Build contexts are always the **project root**.

### Static (no LLM)

```sh
docker build -f build/Docker/static/Dockerfile -t gca .
```

```sh
docker run --rm -v "$(pwd):/repo" gca /repo --base-ref main
```

### LLM

The model is downloaded from Hugging Face during the build and baked into the image — no internet access required at runtime. The model source is read from [`llm-config.yml`](llm-config.yml).

```sh
docker build -f build/Docker/llm/Dockerfile -t gca-llm .
```

```sh
docker run --rm -v "$(pwd):/repo" gca-llm /repo \
  --base-ref main \
  --config /app/llm-config.yml
```

---

## Testing

### Setup

```sh
uv sync --group dev
```

### Unit tests

Run the full suite (excludes integration tests that require a real LLM):

```sh
uv run pytest
```

Run a specific file or test:

```sh
uv run pytest tests/test_checkers.py
uv run pytest tests/test_llm_checker.py -k "test_pass_response_passes"
```

With coverage:

```sh
uv run pytest --cov=git_commit_analyzer --cov-report=term-missing
```

### Integration tests

Integration tests run the LLM checker against a real local model. They require:

1. The `[llm]` extra installed:
   ```sh
   uv sync --extra llm
   ```
2. A valid [`llm-config.yml`](llm-config.yml) pointing at a model (see [LLM checker](#llm-checker)).

```sh
uv run pytest tests/test_llm_integration.py -v
```

The model is loaded once per session. First run downloads it from Hugging Face (~1 GB depending on the model).

To run everything including integration tests:

```sh
uv run pytest -m ""
```

To explicitly skip integration tests:

```sh
uv run pytest -m "not integration"
```

---

## CI integration

### GitLab CI

```yaml
check-commits:
  image: gca
  script:
    - gca analyze . --base-ref $CI_MERGE_REQUEST_DIFF_BASE_SHA --config rules.yml
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### GitHub Actions

```yaml
- name: Check commit messages
  run: |
    gca analyze . \
      --base-ref ${{ github.event.pull_request.base.sha }} \
      --config rules.yml
```
