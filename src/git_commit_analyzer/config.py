"""Application-level configuration parsed from the ``config:`` YAML section."""

from dataclasses import dataclass, field


@dataclass
class LlmConfig:
    """Configuration for the llama-cpp-python LLM checker.

    At least one of :attr:`model_path` or (:attr:`repo_id` + :attr:`filename`)
    must be provided so the checker knows which model to load.

    Attributes:
        prompt: Prompt template sent to the model.  The placeholder ``{commit}``
            is replaced with the subject and/or description of the commit.
            The model must reply with ``PASS`` or ``FAIL`` as the very first word,
            optionally followed by a one-sentence explanation.
        repo_id: Hugging Face repository ID, e.g. ``"Qwen/Qwen2.5-3B-Instruct-GGUF"``.
            Mutually exclusive with :attr:`model_path`.
        filename: GGUF filename or glob pattern within the HF repo,
            e.g. ``"*q4_k_m.gguf"``.  Used together with :attr:`repo_id`.
        model_path: Local filesystem path to a ``.gguf`` model file.
            Mutually exclusive with :attr:`repo_id` / :attr:`filename`.
        context_window: Number of tokens in the model's context window
            (``n_ctx`` llama-cpp option).  Defaults to ``4096``.
        max_tokens: Maximum number of tokens to generate in the response.
            Defaults to ``256``.
        stop: List of stop strings that terminate generation early.
            Defaults to an empty list.
        verbose: Whether llama-cpp should print progress / loading info to
            stderr.  Defaults to ``False``.
    """

    prompt: str
    repo_id: str | None = None
    filename: str | None = None
    model_path: str | None = None
    context_window: int = 4096
    max_tokens: int = 256
    stop: list[str] = field(default_factory=list)
    verbose: bool = False


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
