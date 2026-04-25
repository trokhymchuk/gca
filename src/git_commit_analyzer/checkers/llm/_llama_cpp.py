import warnings

from ...config import LlmConfig
from ._base import LlmBackend


def _load_llama(config: LlmConfig) -> object:
    """Load and return a ``Llama`` instance from *config*.

    Extracted as a module-level function so tests can patch it without
    requiring llama-cpp-python to be installed.

    Raises:
        ImportError: If ``llama-cpp-python`` is not installed.
        ValueError: If neither ``model_path`` nor ``repo_id`` is set.
    """
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise ImportError(
            "llama-cpp-python is required for the llama-cpp backend. "
            "Install it with: pip install 'gca[llm-llama-cpp]'"
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


class LlamaCppBackend(LlmBackend):
    """LLM backend backed by ``llama-cpp-python`` (GGUF models).

    Requires the ``gca[llm-llama-cpp]`` extra::

        pip install 'gca[llm-llama-cpp]'
    """

    def __init__(self, config: LlmConfig) -> None:
        self._llm = _load_llama(config)

    def generate(self, prompt: str, max_tokens: int, stop: list[str]) -> str:
        output = self._llm(
            prompt,
            max_tokens=max_tokens,
            stop=stop or None,
            echo=False,
        )
        return output["choices"][0]["text"].strip()
