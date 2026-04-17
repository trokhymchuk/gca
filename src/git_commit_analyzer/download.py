"""Model download helper for the LLM checker."""

import fnmatch
import warnings
from pathlib import Path


def download_model(repo_id: str, filename_pattern: str) -> Path:
    """Download the first file matching *filename_pattern* from *repo_id*.

    Args:
        repo_id: Hugging Face repository ID, e.g. ``"microsoft/Phi-3-mini-4k-instruct-gguf"``.
        filename_pattern: Glob pattern matched against bare filenames,
            e.g. ``"*q4.gguf"``.

    Returns:
        Local path to the downloaded file inside the HF cache.

    Raises:
        ImportError: If ``huggingface-hub`` is not installed.
        ValueError: If no file in the repo matches *filename_pattern*.
    """
    warnings.filterwarnings(
        "ignore", message=".*unauthenticated.*", category=UserWarning
    )
    warnings.filterwarnings("ignore", message=".*HF_TOKEN.*", category=UserWarning)

    try:
        from huggingface_hub import hf_hub_download, list_repo_files
    except ImportError as exc:
        raise ImportError(
            "huggingface-hub is required. Install with: pip install 'gca[llm]'"
        ) from exc

    match = next(
        (
            f
            for f in list_repo_files(repo_id)
            if fnmatch.fnmatch(f.split("/")[-1], filename_pattern)
        ),
        None,
    )
    if match is None:
        raise ValueError(f"No file matching {filename_pattern!r} found in {repo_id!r}")

    return Path(hf_hub_download(repo_id=repo_id, filename=match))
