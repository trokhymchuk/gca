"""Tests for LlmChecker and related config parsing.

llama-cpp-python is an optional dependency, so _load_llama is patched in every
test — the real inference library is never required.
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from git_commit_analyzer import GitCommit, LlmChecker, load_ruleset
from git_commit_analyzer.config import AppConfig, LlmConfig

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def make_commit(subject: str = "feat: subject") -> GitCommit:
    return GitCommit(
        sha="a" * 40,
        subject=subject,
        body="",
        description="",
        trailers=[],
        parent_shas=[],
        changed_files=[],
        author_name="Test",
        author_email="test@example.com",
        author_date=_NOW,
        committer_name="Test",
        committer_email="test@example.com",
        committer_date=_NOW,
    )


_REAL_PROMPT = """\
<|im_start|>system
You are a senior software engineer reviewing git commit messages.
Evaluate the commit below and respond with PASS or FAIL as the first
word, followed by a one-sentence reason.
Criteria for PASS: clear subject, follows conventional-commits format,
describes the change and its motivation.
Criteria for FAIL: vague, missing context, or does not follow conventions.
<|im_end|>
<|im_start|>user
{commit}
<|im_end|>
<|im_start|>assistant
"""


def make_config(prompt: str = _REAL_PROMPT) -> LlmConfig:
    return LlmConfig(
        repo_id="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        filename="*q4_k_m.gguf",
        context_window=4096,
        max_tokens=60,
        stop=["<|im_end|>"],
        prompt=prompt,
    )


def make_mock_llm(response_text: str) -> MagicMock:
    """Return a mock Llama instance whose __call__ returns the given text."""
    mock = MagicMock()
    mock.return_value = {"choices": [{"text": response_text}]}
    return mock


# ---------------------------------------------------------------------------
# Commit message fixtures
# ---------------------------------------------------------------------------

# Each entry is (subject, description). Both are fed to the LLM checker.
GOOD_COMMITS: list[tuple[str, str]] = [
    (
        "feat(auth): add JWT token refresh with sliding expiration window",
        "Access tokens now refresh automatically when the remaining TTL drops below\n"
        "30 seconds. This prevents mid-session logouts for users on slow connections\n"
        "without requiring a full re-authentication round-trip.",
    ),
    (
        "fix(api): resolve race condition in concurrent request handler",
        "Two goroutines could simultaneously write to the response buffer when the\n"
        "upstream took longer than the client timeout. Added a mutex guard around\n"
        "the write path and added a regression test that reproduces the original race.",
    ),
    (
        "docs(readme): update installation instructions for Python 3.12",
        "Python 3.11 reached end-of-life. Updated the quickstart section to target\n"
        "3.12, removed the outdated virtualenv step, and added the uv-based workflow\n"
        "that matches the project's current tooling.",
    ),
    (
        "refactor(parser): extract commit parsing logic into dedicated module",
        "The parser was embedded inside the CLI entrypoint, making it untestable in\n"
        "isolation. Moving it to parser.py allows unit tests to cover edge cases\n"
        "such as empty bodies, binary content, and malformed trailer blocks.",
    ),
    (
        "fix(db): prevent duplicate inserts under high concurrency using advisory locks",
        "Under load tests we observed duplicate rows when two workers raced on the\n"
        "same idempotency key. Switching to advisory locks in the INSERT path removes\n"
        "the window entirely without adding a separate SELECT before every write.",
    ),
    (
        "perf(indexer): reduce memory usage by 40% via streaming file reads",
        "The indexer previously loaded entire files into memory before parsing.\n"
        "Replacing the bulk read with a line-by-line generator cuts peak RSS from\n"
        "~800 MB to ~480 MB on the largest corpus in the benchmark suite.",
    ),
    (
        "feat(cli): add --output-format flag supporting json, csv, and text",
        "CI pipelines downstream of this tool need machine-readable output.\n"
        "Adding --output-format avoids ad-hoc grep parsing of human text and\n"
        "makes the json and csv paths available without a separate formatter script.",
    ),
    (
        "fix(auth): correct token expiry calculation for non-UTC timezones",
        "datetime.now() returned local time while expiry was stored as UTC epoch.\n"
        "The delta was negative for timezones behind UTC, causing every token to\n"
        "appear expired immediately. All datetime arithmetic now uses timezone-aware\n"
        "objects anchored to UTC.",
    ),
    (
        "chore(deps): bump pyyaml from 6.0.1 to 6.0.2 to address CVE-2024-1234",
        "CVE-2024-1234 allows arbitrary code execution when loading untrusted YAML\n"
        "with the default Loader. Upgrading to 6.0.2 patches the vulnerability.\n"
        "No API changes required; all existing tests pass.",
    ),
    (
        "feat(search): implement full-text search using trigram indexes",
        "LIKE queries on the notes table caused sequential scans above ~100k rows.\n"
        "Adding a GIN trigram index and rewriting the query to use @@ ts_query\n"
        "brings p99 latency from 4.2s down to 38ms on the production dataset.",
    ),
    (
        "fix(parser): handle empty commit body without raising IndexError",
        "git log --format with %b outputs an empty string for commits that have\n"
        "no body. The splitter assumed at least one line was always present.\n"
        "Added an early-return guard and a test covering the empty-body case.",
    ),
    (
        "feat(cache): add Redis-backed session cache with configurable TTL",
        "The in-process dict cache did not survive worker restarts and caused\n"
        "users to be logged out on every deploy. Redis persistence keeps sessions\n"
        "alive across deploys; TTL is read from SESSION_CACHE_TTL_SECONDS env var.",
    ),
    (
        "fix(upload): enforce 50 MB file size limit before writing to disk",
        "Large uploads were streamed to disk before the size check ran, wasting\n"
        "I/O and disk quota. The limit is now enforced by reading Content-Length\n"
        "upfront and rejecting the request before any data is written.",
    ),
    (
        "perf(query): add composite index on (user_id, created_at) for timeline",
        "Timeline queries filter on user_id and sort by created_at. The separate\n"
        "single-column indexes caused the planner to pick a full sort on a large\n"
        "heap fetch. The composite index drops the query from 900ms to under 5ms.",
    ),
    (
        "feat(notifications): send weekly email digest of activity summaries",
        "Users asked for a way to catch up after periods of inactivity without\n"
        "logging in daily. The weekly digest aggregates unread events and sends\n"
        "a single email every Monday at 08:00 UTC via the existing mailer job.",
    ),
    (
        "fix(serializer): preserve timezone info when serializing datetime fields",
        "The JSON serializer called .isoformat() on naive datetimes, dropping\n"
        "timezone context. Downstream consumers silently interpreted times as local\n"
        "zone, causing off-by-hours bugs in multi-region deployments.",
    ),
    (
        "refactor(router): split monolithic router into feature-scoped sub-routers",
        "The single router.py file grew to 1400 lines with mixed concerns.\n"
        "Each feature area (auth, billing, admin) now registers its own APIRouter\n"
        "and is included in the main app with a prefix, improving discoverability.",
    ),
    (
        "feat(pagination): replace offset-based with cursor-based pagination",
        "Offset pagination produces inconsistent pages when records are inserted\n"
        "or deleted between requests. Cursors based on (created_at, id) are stable\n"
        "and also avoid the costly COUNT(*) that blocked on large tables.",
    ),
    (
        "fix(webhook): retry failed deliveries with exponential backoff",
        "Failed webhook deliveries were dropped silently. Retries now follow a\n"
        "2^n * 100ms schedule up to 5 attempts, after which the delivery is marked\n"
        "dead and the operator is notified via the existing alerting channel.",
    ),
    (
        "feat(audit): log all admin actions to append-only audit table",
        "Compliance requires a tamper-evident record of privilege operations.\n"
        "Admin actions now write a signed entry to audit_log before executing.\n"
        "The table uses row-level security so only the audit reader role can SELECT.",
    ),
    (
        "refactor(services): inject dependencies via constructor instead of globals",
        "Module-level singletons made unit testing require monkeypatching sys.modules.\n"
        "Constructor injection makes dependencies explicit, allows fakes in tests,\n"
        "and eliminates import-order-dependent initialisation bugs.",
    ),
    (
        "feat(rbac): introduce role-based access control for API endpoints",
        "All endpoints previously shared the same authentication check with no\n"
        "authorisation layer. RBAC adds viewer/editor/admin roles enforced at the\n"
        "decorator level; existing sessions are migrated to the editor role.",
    ),
    (
        "fix(scheduler): prevent overlapping job runs with a distributed lock",
        "On multi-instance deployments all workers fired the nightly cleanup job\n"
        "simultaneously, causing duplicate side-effects and thundering-herd on the\n"
        "database. A Redis SETNX lock ensures only one instance runs the job.",
    ),
    (
        "feat(metrics): expose Prometheus counters for request rates and errors",
        "The SRE team needs per-endpoint error rates to set SLO burn-rate alerts.\n"
        "Added http_requests_total and http_errors_total counters with method,\n"
        "path, and status_code labels, scraped at /metrics without auth.",
    ),
    (
        "fix(csv-import): skip blank lines instead of treating them as data rows",
        "Exported CSVs from Excel include a trailing newline that was parsed as\n"
        "an empty data row, causing a validation error on the last line of every\n"
        "file. Added a pre-filter that drops rows where all fields are empty.",
    ),
    (
        "feat(graphql): add cursor-based connection type for paginated lists",
        "The flat list type forced clients to implement their own pagination state.\n"
        "The Relay-compatible Connection type exposes edges, pageInfo, and cursors\n"
        "and is backward-compatible because the old list field still resolves.",
    ),
    (
        "fix(session): regenerate session ID after privilege escalation",
        "Failing to rotate the session ID after privilege escalation leaves the\n"
        "application vulnerable to session fixation (OWASP A07). The session is\n"
        "now invalidated and a new one issued immediately after sudo-mode is granted.",
    ),
    (
        "perf(assets): lazy-load images below the fold to improve LCP",
        "Lighthouse flagged 14 off-screen images being loaded eagerly on the\n"
        "dashboard page. Adding loading=lazy to images outside the initial viewport\n"
        "reduces total blocking time by 620ms and improves LCP from 4.1s to 1.9s.",
    ),
    (
        "feat(workspace): allow users to create and switch between workspaces",
        "Enterprise accounts requested project isolation without separate logins.\n"
        "Workspaces provide a namespace boundary for resources and settings while\n"
        "sharing a single authentication identity across all workspaces.",
    ),
    (
        "fix(timeout): increase HTTP client read timeout to 30s for slow upstreams",
        "The report-generation endpoint calls an upstream that can take up to 25s\n"
        "under heavy load. The 10s default timeout caused intermittent 504 errors\n"
        "on valid requests. Timeout is now configurable per upstream in config.yml.",
    ),
    (
        "chore(ci): add matrix build for Python 3.11, 3.12, and 3.13",
        "The project claims compatibility with all three minor versions but only\n"
        "3.11 was tested in CI. Adding a matrix job catches incompatibilities before\n"
        "they reach users, particularly around typing and match-statement syntax.",
    ),
    (
        "feat(2fa): add TOTP-based two-factor authentication with recovery codes",
        "Security audit identified missing MFA as a high-severity finding.\n"
        "TOTP follows RFC 6238 with a 30-second window; ten single-use recovery\n"
        "codes are generated at enrollment and stored as bcrypt hashes.",
    ),
    (
        "fix(filter): prevent SQL injection in dynamic ORDER BY clause",
        "The sort parameter was interpolated directly into the query string.\n"
        "An allowlist of valid column names now validates the input before\n"
        "it reaches the query builder, and a test covers the injection vector.",
    ),
    (
        "feat(batch): process large CSV imports via asynchronous background workers",
        "Importing files larger than ~5000 rows timed out the HTTP request.\n"
        "The upload now stores the file and enqueues a Celery task; the client\n"
        "polls a /jobs/{id}/status endpoint until the import completes.",
    ),
    (
        "fix(cors): restrict allowed origins to configured whitelist in production",
        "The wildcard CORS header was left over from local development and made\n"
        "it into production, allowing any origin to make credentialed requests.\n"
        "Origins are now read from ALLOWED_ORIGINS and validated at startup.",
    ),
    (
        "perf(serializer): replace json.dumps with orjson for 3x throughput gain",
        "The API serialisation path appeared in every flame graph above 8% CPU.\n"
        "orjson is a drop-in replacement that uses a Rust backend; benchmarks show\n"
        "3.1x throughput improvement with identical output for all tested payloads.",
    ),
    (
        "feat(theming): support custom brand colours via CSS custom properties",
        "White-label customers asked to replace the default blue accent colour.\n"
        "CSS custom properties (--color-primary, --color-accent) are now read from\n"
        "the tenant config and injected as a <style> block in the document head.",
    ),
    (
        "fix(signup): trim whitespace from email before uniqueness check",
        "Users copying their email from a document sometimes include a trailing\n"
        "space, causing a duplicate-user error even though the email is unique.\n"
        "The email is now stripped before validation and before storage.",
    ),
    (
        "feat(rate-limit): apply per-user limit of 1000 requests per minute",
        "A handful of API consumers were generating bulk traffic that degraded\n"
        "response times for all other users. The rate limiter uses a sliding window\n"
        "counter in Redis; over-limit requests receive HTTP 429 with Retry-After.",
    ),
    (
        "fix(login): prevent timing attack via constant-time token comparison",
        "String equality short-circuits on the first differing byte, leaking\n"
        "partial token information through response timing. hmac.compare_digest\n"
        "provides constant-time comparison regardless of where strings diverge.",
    ),
    (
        "refactor(tasks): replace threading.Timer with APScheduler for recurring jobs",
        "threading.Timer does not survive exceptions and cannot be inspected or\n"
        "cancelled from outside the spawning thread. APScheduler adds a persistent\n"
        "job store, structured logging, and graceful shutdown on SIGTERM.",
    ),
    (
        "feat(dashboard): add real-time activity feed using Server-Sent Events",
        "Users refreshed the page repeatedly to see new activity. SSE pushes events\n"
        "over a persistent HTTP connection without the overhead of WebSockets.\n"
        "The feed degrades gracefully to polling when EventSource is not available.",
    ),
    (
        "fix(proxy): forward X-Forwarded-For to preserve client IP in access logs",
        "Requests routed through the load balancer showed the proxy IP in logs,\n"
        "breaking geo-IP lookups and rate-limit key derivation. The proxy now\n"
        "appends the original IP and the app reads it with a trusted-proxy allowlist.",
    ),
    (
        "feat(restore): add one-click restore from the most recent 7 daily backups",
        "Operators previously had to SSH into the backup host and run a manual\n"
        "shell script to restore. The new UI lists the last 7 snapshots, shows\n"
        "size and timestamp, and triggers a restore job with a single button click.",
    ),
    (
        "fix(avatar): fall back to initials when Gravatar returns 404",
        "Accounts without a Gravatar showed a broken-image icon in the sidebar.\n"
        "The avatar component now renders a coloured circle with the user's initials\n"
        "when the Gravatar request returns a non-2xx status.",
    ),
    (
        "feat(reports): generate monthly PDF summary with activity trend charts",
        "Finance requested a single-page PDF for board reporting. The generator\n"
        "uses WeasyPrint to render the same HTML template as the web view, so\n"
        "charts and tables stay in sync without a separate rendering code path.",
    ),
    (
        "fix(import): detect and reject circular dependencies in plugin loader",
        "A plugin that imported another plugin caused infinite recursion in the\n"
        "loader, crashing the process with a RecursionError. DFS cycle detection\n"
        "now runs before any plugin is initialised and reports the cycle path.",
    ),
    (
        "refactor(errors): unify error response shape across all API handlers",
        "Clients had to handle three different error JSON structures depending\n"
        "on which handler raised the exception. A single ErrorResponse dataclass\n"
        "is now serialised by a global exception handler for all error types.",
    ),
    (
        "docs(deployment): add Kubernetes manifests and Helm chart usage guide",
        "The deployment docs only covered Docker Compose. Added manifests for\n"
        "Deployment, Service, and HPA resources plus a Helm values reference\n"
        "so teams can deploy to existing clusters without custom scripting.",
    ),
    (
        "feat(onboarding): add interactive tutorial for first-time users",
        "Activation rate for new signups dropped below the 60% threshold.\n"
        "A five-step guided tour highlights the three core actions and surfaces\n"
        "contextual help tooltips; users who complete it activate at 84%.",
    ),
]

# Each entry is (subject, description). Both are fed to the LLM checker.
BAD_COMMITS: list[tuple[str, str]] = [
    ("fix stuff", ""),
    ("update", ""),
    ("changes", "fixed some things"),
    ("WIP", ""),
    ("misc", "various"),
    ("done", "its done"),
    ("ok", ""),
    ("patch", "patch"),
    ("cleanup", "cleaned up"),
    ("temp", "temporary"),
    ("quick fix", ""),
    ("small change", "changed a thing"),
    ("more changes", "even more"),
    ("minor update", ""),
    ("some work", "did some work"),
    ("stuff", "more stuff"),
    ("work in progress", "not done yet"),
    ("fix", ""),
    ("add", "added it"),
    ("remove", ""),
    ("update file", "updated the file"),
    ("fix bug", "fixed the bug"),
    ("add feature", ""),
    ("refactor code", "refactored"),
    ("update tests", "updated"),
    ("whoops", "forgot to add this"),
    ("oops", ""),
    ("typo", "fixed typo"),
    ("lol", "idk"),
    ("wip wip wip", ""),
    ("fixup", "fixup commit"),
    ("1", ""),
    ("final", "final version"),
    ("final_final", ""),
    ("real final", "for real this time"),
    ("please work", ""),
    ("idk", "no idea what happened"),
    ("debug", "added some prints"),
    ("hack", "dirty hack"),
    ("hotfix", ""),
    ("urgent", "URGENT FIX"),
    ("breaking", "broke some stuff"),
    ("no idea", ""),
    ("try again", "another attempt"),
    ("yolo", ""),
    ("commit", "saving progress"),
    ("checkpoint", ""),
    ("bump", "bumped version"),
    ("tweak", "small tweak"),
    ("nit", ""),
]

assert len(GOOD_COMMITS) == 50, f"Expected 50 good commits, got {len(GOOD_COMMITS)}"
assert len(BAD_COMMITS) == 50, f"Expected 50 bad commits, got {len(BAD_COMMITS)}"


# ---------------------------------------------------------------------------
# Parametrized tests
# ---------------------------------------------------------------------------

class TestLlmCheckerWithGoodCommits:
    @pytest.mark.parametrize("subject,description", GOOD_COMMITS)
    def test_passes_when_llm_approves(self, subject: str, description: str):
        checker = LlmChecker(config=make_config())
        mock_llm = make_mock_llm("PASS well-structured commit message")
        with patch("git_commit_analyzer.checkers._load_llama", return_value=mock_llm):
            result = checker(make_commit_with_description(subject, description))
        assert result.passed is True, f"Expected PASS for: {subject!r}"

    @pytest.mark.parametrize("subject,description", GOOD_COMMITS)
    def test_prompt_contains_subject_and_description(self, subject: str, description: str):
        checker = LlmChecker(config=make_config(prompt="Evaluate: {commit}"))
        captured: list[str] = []

        def fake_llm(prompt, **kwargs):
            captured.append(prompt)
            return {"choices": [{"text": "PASS ok"}]}

        with patch("git_commit_analyzer.checkers._load_llama", return_value=MagicMock(side_effect=fake_llm)):
            checker(make_commit_with_description(subject, description))

        assert subject in captured[0], f"Subject missing from prompt for: {subject!r}"
        if description.strip():
            assert description.strip() in captured[0], f"Description missing from prompt for: {subject!r}"


class TestLlmCheckerWithBadCommits:
    @pytest.mark.parametrize("subject,description", BAD_COMMITS)
    def test_fails_when_llm_rejects(self, subject: str, description: str):
        checker = LlmChecker(config=make_config())
        mock_llm = make_mock_llm("FAIL commit message is too vague")
        with patch("git_commit_analyzer.checkers._load_llama", return_value=mock_llm):
            result = checker(make_commit_with_description(subject, description))
        assert result.passed is False, f"Expected FAIL for: {subject!r}"
        assert "vague" in result.message

    @pytest.mark.parametrize("subject,description", BAD_COMMITS)
    def test_prompt_contains_subject(self, subject: str, description: str):
        checker = LlmChecker(config=make_config(prompt="Evaluate: {commit}"))
        captured: list[str] = []

        def fake_llm(prompt, **kwargs):
            captured.append(prompt)
            return {"choices": [{"text": "FAIL too vague"}]}

        with patch("git_commit_analyzer.checkers._load_llama", return_value=MagicMock(side_effect=fake_llm)):
            checker(make_commit_with_description(subject, description))

        assert subject in captured[0], f"Subject missing from prompt for: {subject!r}"


# ---------------------------------------------------------------------------
# LlmChecker — response parsing
# ---------------------------------------------------------------------------

class TestLlmCheckerResponseParsing:
    def _run(self, response_text: str):
        checker = LlmChecker(config=make_config())
        with patch("git_commit_analyzer.checkers._load_llama", return_value=make_mock_llm(response_text)):
            return checker(make_commit())

    def test_pass_response_returns_passing_result(self):
        result = self._run("PASS commit looks good")
        assert result.passed is True
        assert "commit looks good" in result.message

    def test_fail_response_returns_failing_result(self):
        result = self._run("FAIL subject is too vague")
        assert result.passed is False
        assert "subject is too vague" in result.message

    def test_pass_lowercase_treated_as_pass(self):
        assert self._run("pass everything ok").passed is True

    def test_fail_mixed_case(self):
        assert self._run("Fail bad message").passed is False

    def test_ambiguous_response_fails(self):
        result = self._run("I think this is fine")
        assert result.passed is False
        assert "ambiguous" in result.message

    def test_empty_response_fails(self):
        assert self._run("").passed is False

    def test_pass_with_no_explanation(self):
        assert self._run("PASS").passed is True

    def test_fail_with_no_explanation(self):
        assert self._run("FAIL").passed is False


# ---------------------------------------------------------------------------
# LlmChecker — model loading
# ---------------------------------------------------------------------------

class TestLlmCheckerModelLoading:
    def test_llm_loaded_once_across_multiple_calls(self):
        checker = LlmChecker(config=make_config())
        mock_llm = make_mock_llm("PASS ok")
        with patch("git_commit_analyzer.checkers._load_llama", return_value=mock_llm) as mock_load:
            checker(make_commit())
            checker(make_commit())
        mock_load.assert_called_once()

    def test_load_error_becomes_failing_result(self):
        checker = LlmChecker(config=make_config())
        with patch("git_commit_analyzer.checkers._load_llama", side_effect=ImportError("not installed")):
            result = checker(make_commit())
        assert result.passed is False
        assert "not installed" in result.message

    def test_stop_tokens_forwarded_to_llm(self):
        config = LlmConfig(
            prompt="{commit}",
            repo_id="test/model",
            filename="*.gguf",
            stop=["<|im_end|>"],
        )
        checker = LlmChecker(config=config)
        mock_llm = make_mock_llm("PASS")
        with patch("git_commit_analyzer.checkers._load_llama", return_value=mock_llm):
            checker(make_commit())
        _, kwargs = mock_llm.call_args
        assert kwargs.get("stop") == ["<|im_end|>"]

    def test_name(self):
        assert LlmChecker.name == "llm"


# ---------------------------------------------------------------------------
# LlmChecker — include_subject / include_description flags
# ---------------------------------------------------------------------------

def make_commit_with_description(subject: str, description: str) -> GitCommit:
    return GitCommit(
        sha="a" * 40,
        subject=subject,
        body=description,
        description=description,
        trailers=[],
        parent_shas=[],
        changed_files=[],
        author_name="Test",
        author_email="test@example.com",
        author_date=_NOW,
        committer_name="Test",
        committer_email="test@example.com",
        committer_date=_NOW,
    )


class TestCommitTextSelection:
    def _capture_prompt(self, checker: LlmChecker, commit: GitCommit) -> str:
        captured: list[str] = []

        def fake_llm(prompt, **kwargs):
            captured.append(prompt)
            return {"choices": [{"text": "PASS ok"}]}

        with patch("git_commit_analyzer.checkers._load_llama", return_value=MagicMock(side_effect=fake_llm)):
            checker(commit)
        return captured[0]

    def test_subject_included_by_default(self):
        checker = LlmChecker(config=make_config(prompt="{commit}"))
        commit = make_commit_with_description("feat: my feature", "Some description")
        prompt = self._capture_prompt(checker, commit)
        assert "feat: my feature" in prompt

    def test_description_included_by_default(self):
        checker = LlmChecker(config=make_config(prompt="{commit}"))
        commit = make_commit_with_description("feat: my feature", "Some description")
        prompt = self._capture_prompt(checker, commit)
        assert "Some description" in prompt

    def test_subject_only_excludes_description(self):
        checker = LlmChecker(config=make_config(prompt="{commit}"), include_description=False)
        commit = make_commit_with_description("feat: my feature", "Some description")
        prompt = self._capture_prompt(checker, commit)
        assert "feat: my feature" in prompt
        assert "Some description" not in prompt

    def test_description_only_excludes_subject(self):
        checker = LlmChecker(config=make_config(prompt="{commit}"), include_subject=False)
        commit = make_commit_with_description("feat: my feature", "Some description")
        prompt = self._capture_prompt(checker, commit)
        assert "feat: my feature" not in prompt
        assert "Some description" in prompt

    def test_empty_description_not_appended(self):
        checker = LlmChecker(config=make_config(prompt="{commit}"), include_description=True)
        commit = make_commit_with_description("feat: my feature", "")
        prompt = self._capture_prompt(checker, commit)
        assert prompt.strip().endswith("feat: my feature")

    def test_subject_and_description_separated_by_blank_line(self):
        checker = LlmChecker(config=make_config(prompt="{commit}"))
        commit = make_commit_with_description("feat: my feature", "Explains the why.")
        prompt = self._capture_prompt(checker, commit)
        assert "feat: my feature\n\nExplains the why." in prompt

    def test_both_false_produces_empty_commit_text(self):
        checker = LlmChecker(
            config=make_config(prompt="Review: [{commit}]"),
            include_subject=False,
            include_description=False,
        )
        commit = make_commit_with_description("feat: my feature", "Some description")
        prompt = self._capture_prompt(checker, commit)
        assert prompt == "Review: []"

    def test_flags_loaded_from_yaml(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
config:
  llm:
    repo_id: "test/model"
    filename: "*.gguf"
    prompt: "{commit}"
rules:
  - name: llm-review
    checkers:
      - type: llm
        include_subject: true
        include_description: false
""")
        rf = load_ruleset(yaml_file)
        checker = rf.ruleset.rules[0].checkers[0]
        assert isinstance(checker, LlmChecker)
        assert checker.include_subject is True
        assert checker.include_description is False

    def test_flags_default_to_true_in_yaml(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
config:
  llm:
    repo_id: "test/model"
    filename: "*.gguf"
    prompt: "{commit}"
rules:
  - name: llm-review
    checkers:
      - type: llm
""")
        rf = load_ruleset(yaml_file)
        checker = rf.ruleset.rules[0].checkers[0]
        assert checker.include_subject is True
        assert checker.include_description is True


# ---------------------------------------------------------------------------
# _build_config / load_ruleset — config section parsing
# ---------------------------------------------------------------------------

class TestBuildConfig:
    def test_defaults_when_config_absent(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("rules: []\n")
        rf = load_ruleset(yaml_file)
        assert rf.config.exit_code_on_failure == 1
        assert rf.config.debug is False
        assert rf.config.llm is None

    def test_exit_code_parsed(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("config:\n  exit_code_on_failure: 2\nrules: []\n")
        assert load_ruleset(yaml_file).config.exit_code_on_failure == 2

    def test_debug_flag_parsed(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("config:\n  debug: true\nrules: []\n")
        assert load_ruleset(yaml_file).config.debug is True

    def test_llm_config_parsed(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
config:
  llm:
    repo_id: "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
    filename: "*q4_k_m.gguf"
    context_window: 2048
    max_tokens: 60
    stop: ["<|im_end|>"]
    prompt: "Review: {commit}"
rules: []
""")
        llm = load_ruleset(yaml_file).config.llm
        assert llm is not None
        assert llm.repo_id == "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
        assert llm.filename == "*q4_k_m.gguf"
        assert llm.context_window == 2048
        assert llm.max_tokens == 60
        assert llm.stop == ["<|im_end|>"]

    def test_llm_checker_in_rule_requires_llm_config(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("rules:\n  - name: llm-review\n    checkers:\n      - type: llm\n")
        with pytest.raises(ValueError, match="config.llm"):
            load_ruleset(yaml_file)

    def test_llm_checker_instantiated_from_yaml(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
config:
  llm:
    repo_id: "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
    filename: "*q4_k_m.gguf"
    prompt: "Review: {commit}"
rules:
  - name: llm-review
    checkers:
      - type: llm
""")
        rf = load_ruleset(yaml_file)
        checker = rf.ruleset.rules[0].checkers[0]
        assert isinstance(checker, LlmChecker)
        assert checker.config.repo_id == "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
