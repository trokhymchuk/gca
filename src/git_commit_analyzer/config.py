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
        backend: Backend to use for inference.  Local backends:
            ``"llama-cpp"`` (default) uses ``llama-cpp-python`` with GGUF models;
            ``"transformers"`` uses HuggingFace ``transformers`` + ``torch``.
            Remote HTTP API backends: ``"openai"``, ``"anthropic"``,
            ``"deepseek"`` and ``"gemini"`` call a hosted chat API and require
            :attr:`model` plus an API key (see :attr:`api_key` /
            :attr:`api_key_env`).
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
        model: Model name for the HTTP API backends (``openai``, ``anthropic``,
            ``deepseek``, ``gemini``), e.g. ``"gpt-4o-mini"``,
            ``"claude-3-5-sonnet-latest"`` or ``"gemini-2.0-flash"``.  Required
            for those backends and ignored by the local ones.
        api_key: Literal API token for the HTTP API backends.  Prefer
            :attr:`api_key_env` or the provider's default environment variable
            so the secret is not stored in the config file.  Defaults to ``None``.
        api_key_env: Name of the environment variable holding the API token,
            e.g. ``"OPENAI_API_KEY"``.  When neither this nor :attr:`api_key`
            is set, the provider's default variable is used (``OPENAI_API_KEY``,
            ``ANTHROPIC_API_KEY``, ``DEEPSEEK_API_KEY`` or ``GEMINI_API_KEY``).
            Defaults to ``None``.
        base_url: Base URL for the HTTP API backends, e.g.
            ``"https://api.openai.com/v1"``.  When ``None`` the provider's
            default endpoint is used.  Set this to point at a compatible or
            self-hosted gateway.  Defaults to ``None``.
        request_timeout: Timeout in seconds for HTTP API requests.
            Defaults to ``60``.
        temperature: Sampling temperature for the HTTP API backends.  Lower
            values make the verdict more deterministic; ``0`` is recommended for
            the PASS/FAIL classification task so the same commit always gets the
            same answer.  When ``None`` the provider's default is used (which is
            typically high and causes the same commit to flip between PASS and
            FAIL across runs).  Defaults to ``None``.
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
    model: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    request_timeout: int = 60
    temperature: float | None = None


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
