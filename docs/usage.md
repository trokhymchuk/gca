# Usage

## CLI Reference

### `analyze`

Analyzes commits in a git repository against optional rule sets.

```
gca analyze [OPTIONS] [REPO_PATH]
```

`REPO_PATH` defaults to the current directory.

| Option | Short | Default | Description |
|---|---|---|---|
| `--base-ref TEXT` | `-b` | — | Base ref for the commit range (e.g. `main`, `origin/main`, `$CI_MERGE_REQUEST_DIFF_BASE_SHA`). Produces the range `BASE_REF..HEAD_REF`. Without this, only the commit at HEAD is shown. |
| `--head-ref TEXT` | `-H` | `HEAD` | Head ref to analyze. |
| `--format [text\|json]` | `-f` | `text` | Output format. `text` is colorized and human-readable; `json` is structured and suitable for further processing. |
| `--no-merges` | — | `false` | Exclude merge commits from the output. |
| `--config FILE` | `-c` | — | YAML config file. Repeatable — rules are concatenated across files, `config:` fields are merged (last file wins per field, except `debug` where any `true` wins). |

**Examples**

```sh
# Inspect HEAD commit only (no rules)
gca analyze .

# Analyze all commits from main to HEAD
gca analyze . --base-ref main

# Between two explicit refs
gca analyze . --base-ref origin/main --head-ref feature-branch

# GitLab CI
gca analyze . --base-ref $CI_MERGE_REQUEST_DIFF_BASE_SHA --format json

# With rules
gca analyze . --base-ref main --config rules.yml

# Layer configs: org-wide base overridden by project-specific
gca analyze . --base-ref main --config base.yml --config project.yml
```

---

### `download-model`

Downloads a GGUF model from Hugging Face into the local cache. Requires the `llm-llama-cpp` extra.

```
gca download-model [OPTIONS]
```

| Option | Description |
|---|---|
| `--config FILE` | YAML config file — reads `repo_id` and `filename` from `config.llm`. |
| `--repo-id TEXT` | Hugging Face repository ID. |
| `--filename TEXT` | Filename glob pattern (e.g. `'*q4_k_m.gguf'`). |

```sh
gca download-model --config llm-llama-cpp-config.yml
gca download-model --repo-id Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF --filename '*q4_k_m.gguf'
```

---

## Config File

A YAML file with two top-level sections: `config:` (optional) and `rules:`.

```yaml
config:
  exit_code_on_failure: 1   # exit code when any rule fails (default: 1)
  debug: false              # print prompts/responses to stderr

rules:
  - name: my-rule
    filters:                # optional — skip commits that don't match
      - type: <filter-type>
        ...
    checkers:               # what to enforce on matched commits
      - type: <checker-type>
        ...
```

**Rule evaluation:**

- A commit passes through a rule's **filters** (all must match — AND logic). If any filter fails the rule is skipped entirely; it is not a failure.
- All **checkers** run on commits that pass the filters. Failures are collected, not short-circuited.
- Any checker or filter can be negated with `invert: true`.

**Config merging** (multiple `--config` files):

- `rules:` lists are concatenated in order.
- `config:` fields are last-wins per key, except `debug` which is OR (any `true` wins).

### `config.llm` section

Required when using the `llm` checker.

```yaml
config:
  llm:
    backend: llama-cpp          # or: transformers

    # llama-cpp: download from Hugging Face on first use
    repo_id: "owner/repo-name"
    filename: "*q4_k_m.gguf"   # glob matched against repo files

    # llama-cpp: or use a local GGUF file
    # model_path: /models/model.gguf

    # transformers: local directory with AutoModelForSequenceClassification
    # model_path: /opt/output_classifier_production
    # device: cpu               # cpu | cuda | mps (default: cpu)

    prompt: "{commit}"          # prompt template; {commit} is replaced
    context_window: 4096
    max_tokens: 60
    stop: ["<|im_end|>"]
    verbose: false
```

---

## Filters

Filters control which commits a rule applies to. All filters on a rule must pass (AND). Add `invert: true` to any filter to negate it.

### `commit_type`

Matches commits by type.

| Parameter | Description |
|---|---|
| `types` | List of one or more types. Valid values: `regular`, `merge`, `revert`, `fixup`, `squash`, `amend`. |

```yaml
# Apply rule only to regular commits (not merges, fixups, etc.)
filters:
  - type: commit_type
    types: [regular]

# Apply rule to everything except merges
filters:
  - type: commit_type
    types: [merge]
    invert: true
```

### `subject_prefix`

Matches commits based on their subject prefix chain. A prefix chain is the sequence of `token:` labels before the description (e.g. `ci: cram: fix typo` has chain `["ci", "cram"]`). Both conventional (`type(scope): …`) and plain (`type: …`) formats are recognized.

| Parameter | Description |
|---|---|
| `any_of` | List of chain patterns. Passes if the commit's chain matches **any** pattern. Each pattern is a list of consecutive tokens. |
| `all_of` | List of chain patterns. Passes if the commit's chain matches **all** patterns. |

At least one of `any_of` or `all_of` must be provided.

```yaml
# Match commits prefixed with feat: or fix:
filters:
  - type: subject_prefix
    any_of: [["feat"], ["fix"]]

# Match commits prefixed with ci: cram:
filters:
  - type: subject_prefix
    any_of: [["ci", "cram"]]
```

### `paths_modified`

Matches commits based on which files were changed.

| Parameter | Description |
|---|---|
| `any_of` | Passes if **at least one** listed path matches a changed file. |
| `all_of` | Passes if **every** listed path has at least one matching changed file. |

Path entry formats:
- Ending with `/` → directory prefix (matches any file under that directory)
- Contains `*`, `?`, or `[` → glob pattern (`fnmatch`)
- Otherwise → exact file path

```yaml
# Apply only to commits that touch src/
filters:
  - type: paths_modified
    any_of: [src/]

# Apply only when both src/ and tests/ are modified
filters:
  - type: paths_modified
    all_of: [src/, tests/]
```

---

## Checkers

Checkers define what must be true about a commit that passed its filters. Add `invert: true` to negate any checker.

### Subject

#### `subject_length`

Enforces character length bounds on the subject line.

| Parameter | Description |
|---|---|
| `min` | Minimum number of characters (optional). |
| `max` | Maximum number of characters (optional). |

At least one of `min` or `max` must be provided.

```yaml
checkers:
  - type: subject_length
    min: 10
    max: 72
```

#### `subject_matches_regex`

Subject must match a regular expression (`re.search`).

| Parameter | Description |
|---|---|
| `pattern` | Regular expression pattern. |

```yaml
# Subject must reference a ticket number
checkers:
  - type: subject_matches_regex
    pattern: "\\bJIRA-\\d+"

# Subject must NOT contain WIP
checkers:
  - type: subject_matches_regex
    pattern: "(?i)\\bwip\\b"
    invert: true
```

#### `subject_prefix`

Validates the subject prefix chain.

| Parameter | Description |
|---|---|
| `require_prefix` | Fail if no prefix is found (default: `true`). |
| `conventional` | Require `type(scope): …` format (default: `false`). |
| `required` | The chain must match at least one of these patterns (OR). Each inner list is a consecutive subsequence that must appear in the chain. |
| `whitelist` | Allowed chains (exact match). Sets mode to `whitelist` if provided without `mode`. |
| `blacklist` | Forbidden chains (exact match). Sets mode to `blacklist` if provided without `mode`. |
| `mode` | `whitelist` or `blacklist`. Required when both `whitelist` and `blacklist` are provided. |

```yaml
# Require any conventional-commits prefix
checkers:
  - type: subject_prefix
    require_prefix: true
    conventional: true

# Restrict to an allowed set of prefixes
checkers:
  - type: subject_prefix
    whitelist:
      - [feat]
      - [fix]
      - [chore]
      - [docs]
      - [ci]
      - [test]
      - [refactor]

# Forbid WIP commits
checkers:
  - type: subject_prefix
    blacklist: [[wip]]
```

### Description

#### `description_length`

Enforces length constraints on the commit description (body).

| Parameter | Description |
|---|---|
| `min` | Minimum total character count (optional). |
| `line_max` | Maximum characters per line (optional). |

```yaml
checkers:
  - type: description_length
    min: 20
    line_max: 100
```

#### `description_matches_regex`

Description must match a regular expression (`re.search`).

| Parameter | Description |
|---|---|
| `pattern` | Regular expression pattern. |

```yaml
checkers:
  - type: description_matches_regex
    pattern: "(?i)\\b(because|reason|why|in order to)\\b"
```

### Trailers

Git trailers are structured key-value lines at the end of the commit body, e.g. `Signed-off-by: Alice <alice@example.com>`. Token matching is case-insensitive.

#### `trailer_present`

Flexible trailer presence validation.

| Parameter | Description |
|---|---|
| `required` | All listed tokens must be present and non-empty. |
| `at_least_one_of` | List of groups. For each group, at least one token must be present. |
| `exactly_one_of` | List of groups. For each group, exactly one token must be present. |
| `whitelist` | Additional allowed tokens (relevant in whitelist mode). |
| `blacklist` | Tokens that must not appear. |
| `mode` | `whitelist` — only tokens from `required` / `at_least_one_of` / `exactly_one_of` / `whitelist` are permitted. `blacklist` (default) — all tokens are allowed except those in `blacklist`. Must be explicit when both `whitelist` and `blacklist` are set. |

```yaml
# Must have Signed-off-by
checkers:
  - type: trailer_present
    required: [Signed-off-by]

# Must have exactly one of Reviewed-by or Acked-by
checkers:
  - type: trailer_present
    exactly_one_of:
      - [Reviewed-by, Acked-by]

# Only allow known trailers (strict whitelist)
checkers:
  - type: trailer_present
    required: [Signed-off-by]
    whitelist: [Reviewed-by, Co-authored-by]
    mode: whitelist
```

#### `trailer_can_merge`

Ensures listed trailers appear at most once.

| Parameter | Description |
|---|---|
| `trailers` | List of trailer tokens. Each must appear at most once. |

```yaml
checkers:
  - type: trailer_can_merge
    trailers: [Reviewed-by, Approved-by]
```

### Files

#### `paths_modified`

Validates which files a commit modifies.

| Parameter | Description |
|---|---|
| `required` | These paths must be modified. Entries ending with `/` are directory prefixes; otherwise exact file paths. |
| `whitelist` | Allowed paths. Sets mode to `whitelist` if provided without `mode`. |
| `blacklist` | Forbidden paths. Sets mode to `blacklist` if provided without `mode`. |
| `mode` | `whitelist` or `blacklist`. Required when both are provided. |

```yaml
# Changes to src/ must also include a test change
checkers:
  - type: paths_modified
    required: [tests/]

# Migration commits must only touch the migrations directory
checkers:
  - type: paths_modified
    whitelist: [db/migrations/]

# Commits must not modify generated files
checkers:
  - type: paths_modified
    blacklist: [generated/]
```

#### `isolate_changes`

Enforces that file changes stay within defined isolation groups. If any changed file matches a group, all changed files must fit within a single group. Files not matched by any group are free to mix with each other, but not with grouped files.

| Parameter | Description |
|---|---|
| `groups` | List of path groups. Each group is a list of paths (directory prefixes or exact paths). The most specific matching path wins. |

```yaml
# Keep frontend and backend changes separate
checkers:
  - type: isolate_changes
    groups:
      - [frontend/, package.json, package-lock.json]
      - [backend/, requirements.txt]

# Database migrations must not mix with application code
checkers:
  - type: isolate_changes
    groups:
      - [db/migrations/]
      - [src/, tests/]
```

### LLM

Runs a local language model to review the commit. The model must respond with `PASS` or `FAIL` as its first word. Requires the `llm-llama-cpp` or `llm-transformers` extra and a `config.llm` section.

| Parameter | Description |
|---|---|
| `include_subject` | Include the commit subject in the `{commit}` placeholder (default: `true`). |
| `include_description` | Include the commit description in the `{commit}` placeholder (default: `true`). |

```yaml
config:
  llm:
    backend: llama-cpp
    repo_id: "unsloth/Phi-4-mini-instruct-GGUF"
    filename: "*Q5_K_M.gguf"
    context_window: 4096
    max_tokens: 60
    stop: ["<|im_end|>"]
    verbose: false
    prompt: |
      <|im_start|>system
      You are a senior software engineer reviewing git commit messages.
      Respond with PASS or FAIL as the very first word, followed by a one-sentence reason.

      PASS if the subject is specific, uses a conventional-commits prefix,
      and the description explains why the change was made.
      FAIL if the subject is vague, missing a prefix, or has fewer than 10 meaningful characters.
      <|im_end|>
      <|im_start|>user
      {commit}
      <|im_end|>
      <|im_start|>assistant

rules:
  - name: llm-review
    filters:
      - type: commit_type
        types: [regular]
    checkers:
      - type: llm
        include_subject: true
        include_description: true
```

Pre-download the model before first use:

```sh
gca download-model --config llm-llama-cpp-config.yml
```

---

## Full Example Config

```yaml
config:
  exit_code_on_failure: 1

rules:
  # All commits: enforce conventional-commits prefix and subject length
  - name: subject-format
    checkers:
      - type: subject_prefix
        require_prefix: true
        whitelist:
          - [feat]
          - [fix]
          - [chore]
          - [docs]
          - [ci]
          - [test]
          - [refactor]
          - [perf]
      - type: subject_length
        min: 10
        max: 72

  # Regular commits: require a description
  - name: require-description
    filters:
      - type: commit_type
        types: [regular]
    checkers:
      - type: description_length
        min: 20

  # src/ changes must be accompanied by a test change
  - name: src-needs-tests
    filters:
      - type: paths_modified
        any_of: [src/]
    checkers:
      - type: paths_modified
        required: [tests/]

  # Migration commits must be isolated
  - name: migrations-isolated
    filters:
      - type: paths_modified
        any_of: [db/migrations/]
    checkers:
      - type: isolate_changes
        groups:
          - [db/migrations/]

  # Require sign-off on all regular commits
  - name: require-sign-off
    filters:
      - type: commit_type
        types: [regular]
    checkers:
      - type: trailer_present
        required: [Signed-off-by]
```

---

## CI Integration

### GitLab CI

```yaml
check-commits:
  image: ghcr.io/trokhymchuk/gca-static:latest
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
