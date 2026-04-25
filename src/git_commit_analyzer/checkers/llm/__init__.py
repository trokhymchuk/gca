import sys
from dataclasses import dataclass, field

from ...config import LlmConfig
from ...models import GitCommit
from ..base import CheckResult, CommitChecker
from ._base import LlmBackend


def _load_backend(config: LlmConfig) -> LlmBackend:
    """Instantiate and return the backend specified by *config.backend*.

    Extracted as a module-level function so tests can patch it without
    requiring the optional dependencies to be installed.

    Raises:
        ValueError: If *config.backend* is not a recognised backend name.
    """
    if config.backend == "llama-cpp":
        from ._llama_cpp import LlamaCppBackend

        return LlamaCppBackend(config)
    if config.backend == "transformers":
        from ._transformers import TransformersBackend

        return TransformersBackend(config)
    raise ValueError(
        f"Unknown LLM backend: {config.backend!r}. "
        "Supported backends: 'llama-cpp', 'transformers'"
    )


# Requires config.llm section and a backend extra.
#
# llama-cpp (default):
#   pip install 'gca[llm-llama-cpp]'
#
# pytorch-transformers:
#   pip install 'gca[llm-transformers]'
#
# config:
#   llm:
#     backend: llama-cpp          # or: transformers
#     repo_id: "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
#     filename: "qwen2.5-0.5b-instruct-q4_k_m.gguf"
#     prompt: |
#       Does this commit message follow conventional commits?
#       Reply with PASS or FAIL followed by a one-sentence reason.
#       Commit: {commit}
#
# rules:
#   - name: llm-conventional-check
#     checkers:
#       - type: llm
#         include_subject: true
#         include_description: false
@dataclass
class LlmChecker(CommitChecker):
    """Evaluates a commit using a language model via a configurable backend.

    The model receives a rendered prompt (with ``{commit}`` substituted) and
    must reply with ``PASS`` or ``FAIL`` as the first word.  Everything after
    that word is treated as a one-sentence explanation and surfaced in the
    :class:`CheckResult` message.

    The backend is loaded lazily on the first call and cached for subsequent
    commits, so the expensive model load happens at most once per checker
    instance.

    Supported backends (set via ``config.llm.backend``):

    * ``"llama-cpp"`` — local GGUF models via ``llama-cpp-python``
      (install ``gca[llm-llama-cpp]``).
    * ``"transformers"`` — HuggingFace models via ``transformers`` + ``torch``
      (install ``gca[llm-transformers]``).

    Attributes:
        config: LLM connection and generation settings.
        include_subject: When ``True``, the commit subject line is included in
            the ``{commit}`` substitution.  Defaults to ``True``.
        include_description: When ``True``, the commit description is appended
            after the subject.  Ignored when the description is empty.
            Defaults to ``True``.
        debug: When ``True``, the rendered prompt and raw model response are
            printed to *stderr*.
    """

    name = "llm"

    config: LlmConfig
    include_subject: bool = True
    include_description: bool = True
    debug: bool = False
    _backend: LlmBackend | None = field(
        default=None, init=False, repr=False, compare=False
    )

    def _get_backend(self) -> LlmBackend:
        """Return the cached backend, loading it on first access."""
        if self._backend is None:
            self._backend = _load_backend(self.config)
        return self._backend

    def _build_commit_text(self, commit: GitCommit) -> str:
        parts: list[str] = []
        if self.include_subject:
            parts.append(commit.subject)
        if self.include_description and commit.description.strip():
            parts.append(commit.description.strip())
        return "\n\n".join(parts)

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Evaluate *commit* with the configured language model backend.

        Args:
            commit: The commit to evaluate.

        Returns:
            Passing result when the model responds with ``PASS``.
            Failing result with the model's explanation when it responds with
            ``FAIL``, or an error message if the backend is unavailable or the
            response is ambiguous.
        """
        commit_text = self._build_commit_text(commit)
        prompt = self.config.prompt.format(commit=commit_text)

        if self.debug:
            print(
                f"[debug] llm_checker backend={self.config.backend!r} "
                f"model={self.config.repo_id or self.config.model_path!r}",
                file=sys.stderr,
            )
            print(f"[debug] llm_checker prompt:\n{prompt}", file=sys.stderr)

        try:
            backend = self._get_backend()
            response = backend.generate(
                prompt, self.config.max_tokens, self.config.stop
            )
        except Exception as exc:
            return CheckResult.fail(f"LLM check error: {exc}")

        if self.debug:
            print(f"[debug] llm_checker response: {response!r}", file=sys.stderr)

        tokens = response.split(None, 1)
        if not tokens:
            return CheckResult.fail(
                f"LLM returned an ambiguous response (expected PASS or FAIL): {response!r}"
            )
        verdict = tokens[0].upper().rstrip(":.,;!")
        reason = tokens[1].lstrip(":—- ") if len(tokens) > 1 else ""

        if verdict == "PASS":
            return CheckResult.ok(f"PASS — {reason}".rstrip(" —") if reason else "PASS")
        if verdict == "FAIL":
            return CheckResult.fail(
                f"FAIL — {reason}".rstrip(" —") if reason else "FAIL"
            )
        return CheckResult.fail(
            f"LLM returned an ambiguous response (expected PASS or FAIL): {response!r}"
        )
