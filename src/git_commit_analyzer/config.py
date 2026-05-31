"""Application-level configuration parsed from the ``config:`` YAML section."""

from dataclasses import dataclass, field


@dataclass
class LlmConfig:
    """Configuration for the LLM checker.

    At least one of :attr:`model_path` or (:attr:`repo_id` + :attr:`filename`)
    must be provided so the checker knows which model to load.

    Attributes:
        prompt: Prompt template sent to the model.  The placeholder ``{commit}``
            is replaced with the subject and/or description of the commit.
            The model must reply with ``PASS`` or ``FAIL`` as the very first word,
            optionally followed by a one-sentence explanation.
        backend: Backend to use for inference.  ``"llama-cpp"`` (default) uses
            ``llama-cpp-python`` with GGUF models; ``"transformers"`` uses
            HuggingFace ``transformers`` + ``torch``.
        repo_id: Hugging Face repository ID, e.g. ``"Qwen/Qwen2.5-3B-Instruct-GGUF"``.
            Mutually exclusive with :attr:`model_path`.
        filename: GGUF filename or glob pattern within the HF repo,
            e.g. ``"*q4_k_m.gguf"``.  Used together with :attr:`repo_id` for
            the ``llama-cpp`` backend.
        model_path: Local filesystem path to a model file or directory.
            Mutually exclusive with :attr:`repo_id` / :attr:`filename`.
        context_window: Number of tokens in the model's context window
            (``n_ctx`` llama-cpp option).  Defaults to ``4096``.
        max_tokens: Maximum number of tokens to generate in the response.
            Defaults to ``256``.
        stop: List of stop strings that terminate generation early.
            Defaults to an empty list.
        verbose: Whether the backend should print loading info to stderr.
            Defaults to ``False``.
        device: Device to run inference on for the ``transformers`` backend,
            e.g. ``"cpu"``, ``"cuda"``, or ``"mps"``.  Defaults to ``"cpu"``.
        threshold: Minimum positive-class probability required to pass for the
            ``transformers`` backend.  Commits whose score is below this value
            are rejected.  Defaults to ``0.5``.
        fail_message: Custom message printed before the score and threshold when
            a commit is rejected by the ``transformers`` backend.  When empty
            only the score and threshold are shown.  Defaults to ``""``.
    """

    prompt: str
    backend: str = "llama-cpp"
    repo_id: str | None = None
    filename: str | None = None
    model_path: str | None = None
    context_window: int = 4096
    max_tokens: int = 256
    stop: list[str] = field(default_factory=list)
    verbose: bool = False
    device: str = "cpu"
    threshold: float = 0.5
    fail_message: str = ""


@dataclass
class AppConfig:
    """Top-level application configuration from the ``config:`` YAML section.

    Attributes:
        exit_code_on_failure: Process exit code when one or more rule checks
            fail.  Defaults to ``1``.
        debug: When ``True``, extra diagnostic information (commits being
            checked, LLM prompts and raw responses) is printed to *stderr*.
            Defaults to ``False``.
        llm: Optional LLM configuration block.  Required when any rule uses
            the ``llm`` checker type.
    """

    exit_code_on_failure: int = 1
    debug: bool = False
    llm: LlmConfig | None = None
