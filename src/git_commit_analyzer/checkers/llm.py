import sys
import warnings
from dataclasses import dataclass, field

from ..config import LlmConfig
from ..models import GitCommit
from .base import CheckResult, CommitChecker


def _load_llama(config: LlmConfig) -> object:
    """Load and return a ``Llama`` instance from the given configuration.

    Extracted as a module-level function so that tests can patch it without
    requiring llama-cpp-python to be installed.

    Args:
        config: LLM configuration specifying the model source and parameters.

    Returns:
        A ready-to-call ``llama_cpp.Llama`` instance.

    Raises:
        ImportError: If ``llama-cpp-python`` is not installed.
        ValueError: If neither ``model_path`` nor ``repo_id`` is set.
    """
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise ImportError(
            "llama-cpp-python is required for the llm checker. "
            "Install it with: pip install 'gca[llm]'"
        ) from exc

    if config.model_path:
        return Llama(
            model_path=config.model_path,
            n_ctx=config.context_window,
            verbose=config.verbose,
        )
    if config.repo_id:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message=".*local_dir_use_symlinks.*", category=UserWarning
            )
            return Llama.from_pretrained(
                repo_id=config.repo_id,
                filename=config.filename,
                n_ctx=config.context_window,
                verbose=config.verbose,
            )
    raise ValueError("LlmConfig requires either 'model_path' or 'repo_id' to be set")


# Requires config.llm section and the gca[llm] extra (pip install 'gca[llm]').
#
# config:
#   llm:
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
    """Evaluates a commit using a local GGUF language model via llama-cpp-python.

    The model receives a rendered prompt (with ``{commit}`` substituted) and must
    reply with ``PASS`` or ``FAIL`` as the first word.  Everything after that word
    is treated as a one-sentence explanation and surfaced in the
    :class:`CheckResult` message.

    The model is loaded lazily on the first call and cached for subsequent
    commits, so the expensive load happens at most once per checker instance.

    Requires ``llama-cpp-python`` to be installed (optional dependency)::

        pip install 'gca[llm]'

    Attributes:
        config: LLM connection and generation settings.
        include_subject: When ``True``, the commit subject line is included in
            the text substituted for ``{commit}`` in the prompt.  Defaults to
            ``True``.
        include_description: When ``True``, the commit description (body without
            trailers) is appended after the subject in the ``{commit}``
            substitution.  Ignored when the description is empty.  Defaults to
            ``True``.
        debug: When ``True``, the rendered prompt and raw model response are
            printed to *stderr* before the result is returned.
    """

    name = "llm"

    config: LlmConfig
    include_subject: bool = True
    include_description: bool = True
    debug: bool = False
    _llm: object = field(default=None, init=False, repr=False, compare=False)

    def _get_llm(self) -> object:
        """Return the cached ``Llama`` instance, loading it on first access."""
        if self._llm is None:
            self._llm = _load_llama(self.config)
        return self._llm

    def _build_commit_text(self, commit: GitCommit) -> str:
        """Build the text substituted for ``{commit}`` in the prompt.

        Args:
            commit: The commit being evaluated.

        Returns:
            A string containing the subject and/or description as configured.
            Returns an empty string when both flags are ``False``.
        """
        parts: list[str] = []
        if self.include_subject:
            parts.append(commit.subject)
        if self.include_description and commit.description.strip():
            parts.append(commit.description.strip())
        return "\n\n".join(parts)

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Evaluate *commit* with the configured local language model.

        Formats the prompt template (substituting ``{commit}`` with the
        selected commit text), runs inference, then parses the first word of
        the response as ``PASS`` or ``FAIL``.

        Args:
            commit: The commit to evaluate.

        Returns:
            Passing result when the model responds with ``PASS``.
            Failing result with the model's explanation when it responds with
            ``FAIL``, or an error message if the model is unavailable or the
            response is ambiguous.
        """
        commit_text = self._build_commit_text(commit)
        prompt = self.config.prompt.format(commit=commit_text)

        if self.debug:
            print(
                f"[debug] llm_checker model={self.config.repo_id or self.config.model_path!r}",
                file=sys.stderr,
            )
            print(f"[debug] llm_checker prompt:\n{prompt}", file=sys.stderr)

        try:
            llm = self._get_llm()
            output = llm(
                prompt,
                max_tokens=self.config.max_tokens,
                stop=self.config.stop or None,
                echo=False,
            )
            response: str = output["choices"][0]["text"].strip()
        except Exception as exc:
            return CheckResult.fail(f"LLM check error: {exc}")

        if self.debug:
            print(f"[debug] llm_checker response: {response!r}", file=sys.stderr)

        # Parse PASS or FAIL as the first word (case-insensitive).
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
