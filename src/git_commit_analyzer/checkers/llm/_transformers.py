from ...config import LlmConfig
from ._base import LlmBackend


class TransformersBackend(LlmBackend):
    """Backend for fine-tuned sequence classifiers via ``transformers`` + ``torch``.

    Loads an ``AutoModelForSequenceClassification`` model from a local
    directory (e.g. ``output_classifier/``) or a HuggingFace Hub repo ID.
    The commit text is tokenised and forwarded through the classifier; the
    positive-class probability (label index ``1``) determines the verdict.

    The ``max_tokens`` and ``stop`` arguments from
    :meth:`~._base.LlmBackend.generate` are not used — they are irrelevant
    for a classifier.

    Requires the ``gca[llm-transformers]`` extra::

        pip install 'gca[llm-transformers]'
    """

    def __init__(self, config: LlmConfig) -> None:
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "transformers and torch are required for the transformers backend. "
                "Install them with: pip install 'gca[llm-transformers]'"
            ) from exc

        model_id = config.model_path or config.repo_id
        if not model_id:
            raise ValueError(
                "LlmConfig requires either 'model_path' or 'repo_id' to be set"
            )

        self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_id)
        self._model.eval()
        self._model.to(config.device)

    def generate(self, prompt: str, max_tokens: int, stop: list[str]) -> str:
        import torch
        import torch.nn.functional as F

        inputs = self._tokenizer(
            prompt,
            return_tensors="pt",
            max_length=256,
            truncation=True,
        ).to(self._model.device)

        with torch.no_grad():
            logits = self._model(**inputs).logits
            probs = F.softmax(logits, dim=-1)[0]

        good_prob = probs[1].item()
        confidence = round(max(good_prob, 1 - good_prob) * 100, 1)
        if good_prob >= 0.5:
            return f"PASS {confidence}% confidence"
        return f"FAIL {confidence}% confidence"
