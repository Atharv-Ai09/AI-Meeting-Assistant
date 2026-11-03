"""Abstractive meeting summarisation with Hugging Face Transformers.

A lightweight distilled BART model is used by default. It is loaded lazily,
runs on CPU (or GPU when available) and handles long transcripts by
summarising chunks and combining the chunk summaries.
"""
import logging
import threading

from utils.text_utils import chunk_text, clean_text, count_words

logger = logging.getLogger(__name__)

LENGTH_PRESETS = {
    "short": {"max_length": 60, "min_length": 20},
    "medium": {"max_length": 130, "min_length": 40},
    "detailed": {"max_length": 220, "min_length": 80},
}

_state = {"name": None, "device": None, "tokenizer": None, "model": None}
_lock = threading.Lock()


class SummarizationModelError(RuntimeError):
    """The summarisation model could not be loaded or run."""


def is_loaded():
    return _state["model"] is not None


def loaded_model_name():
    return _state["name"]


def load_model(model_name="sshleifer/distilbart-cnn-12-6", device_preference="auto"):
    """Load (or return the cached) tokenizer and model."""
    with _lock:
        if _state["model"] is not None and _state["name"] == model_name:
            return _state["tokenizer"], _state["model"], _state["device"]
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise SummarizationModelError(
                "The 'transformers' or 'torch' package is not installed. Run: pip install -r requirements.txt"
            ) from exc

        pref = (device_preference or "auto").lower()
        device = "cuda" if pref != "cpu" and torch.cuda.is_available() else "cpu"
        logger.info(
            "Loading summarisation model '%s' on %s. The first run downloads it and may take a few minutes.",
            model_name, device,
        )
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            model.to(device)
            model.eval()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Summarisation model load failed")
            raise SummarizationModelError(
                f"Could not load the summarisation model '{model_name}'. Check your internet connection "
                "(needed for the first download), free disk space and available memory."
            ) from exc
        _state.update(name=model_name, device=device, tokenizer=tokenizer, model=model)
        return tokenizer, model, device


def _generate(text, length, model_name, device_preference):
    import torch

    preset = LENGTH_PRESETS[length]
    tokenizer, model, device = load_model(model_name, device_preference)
    prompt = ("summarize: " + text) if "t5" in model_name.lower() else text
    limit = min(int(getattr(tokenizer, "model_max_length", 1024) or 1024), 1024)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=limit).to(device)
    input_len = int(inputs["input_ids"].shape[1])
    max_len = min(preset["max_length"], max(16, int(input_len * 0.8)))
    min_len = min(preset["min_length"], max(8, max_len // 2))
    try:
        with torch.no_grad():
            output = model.generate(
                **inputs, max_length=max_len, min_length=min_len, num_beams=4,
                length_penalty=2.0, no_repeat_ngram_size=3, early_stopping=True,
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Summarisation inference failed")
        raise SummarizationModelError("Summarisation failed while processing the transcript.") from exc
    return tokenizer.decode(output[0], skip_special_tokens=True).strip()


def summarize_text(text, length="medium", chunk_words=350, model_name="sshleifer/distilbart-cnn-12-6",
                   device_preference="auto"):
    """Summarise a transcript of any length.

    Long transcripts are split into chunks, each chunk is summarised and the
    chunk summaries are combined (and condensed again for short/medium).
    """
    if length not in LENGTH_PRESETS:
        raise ValueError("Unknown summary length.")
    text = clean_text(text)
    if not text:
        raise ValueError("The transcript is empty.")

    chunks = chunk_text(text, max_words=chunk_words)
    summaries = [_generate(chunk, length, model_name, device_preference) for chunk in chunks]
    if len(chunks) == 1:
        return summaries[0]

    combined = " ".join(summaries)
    depth = 0
    while count_words(combined) > chunk_words and depth < 3:
        parts = chunk_text(combined, max_words=chunk_words)
        if len(parts) <= 1:
            break
        combined = " ".join(_generate(p, length, model_name, device_preference) for p in parts)
        depth += 1
    if length != "detailed":
        combined = _generate(combined, length, model_name, device_preference)
    return combined.strip()
