"""Speech recognition with OpenAI Whisper (open-source, runs locally).

The model is loaded lazily on first use and then reused for later requests.
CPU is used by default when no GPU is available.
"""
import gc
import logging
import threading

from utils.audio_processing import load_audio_array, normalize_audio
from utils.text_utils import join_transcripts

logger = logging.getLogger(__name__)

_models = {}
_lock = threading.Lock()


class ModelLoadError(RuntimeError):
    """The Whisper model (or PyTorch/Whisper itself) could not be loaded."""


class TranscriptionError(RuntimeError):
    """Transcription failed."""


class NoSpeechDetectedError(TranscriptionError):
    """The audio contained no recognisable speech."""


def resolve_device(preference="auto"):
    """Return 'cuda' when requested/available, otherwise 'cpu'."""
    preference = (preference or "auto").lower()
    if preference == "cpu":
        return "cpu"
    try:
        import torch
    except ImportError as exc:
        raise ModelLoadError(
            "PyTorch is not installed. Run: pip install -r requirements.txt"
        ) from exc
    if torch.cuda.is_available():
        return "cuda"
    if preference == "cuda":
        logger.warning("CUDA requested but not available; using CPU.")
    return "cpu"


def loaded_models():
    """Names of the Whisper models currently held in memory."""
    return [f"{name} ({device})" for name, device in _models]


def load_model(model_name="base", device_preference="auto"):
    """Load (or return the cached) Whisper model."""
    device = resolve_device(device_preference)
    key = (model_name, device)
    with _lock:
        if key in _models:
            return _models[key]
        try:
            import whisper
        except ImportError as exc:
            raise ModelLoadError(
                "The 'openai-whisper' package is not installed. Run: pip install -r requirements.txt"
            ) from exc
        logger.info(
            "Loading Whisper '%s' on %s. The first run downloads the model and may take a few minutes.",
            model_name, device,
        )
        try:
            model = whisper.load_model(model_name, device=device)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Whisper model load failed")
            raise ModelLoadError(
                f"Could not load the Whisper '{model_name}' model. Check your internet connection "
                "(needed for the first download), free disk space and available memory."
            ) from exc
        _models.clear()  # keep only one model in memory on student laptops
        gc.collect()
        _models[key] = model
        return model


def transcribe_audio(audio, model_name="base", language=None, device_preference="auto"):
    """Transcribe a 16 kHz mono WAV path or a float32 numpy array.

    Returns {"text", "language", "segments"}.
    """
    model = load_model(model_name, device_preference)
    try:
        samples = load_audio_array(audio) if isinstance(audio, (str, bytes)) or hasattr(audio, "__fspath__") else audio
        samples = normalize_audio(samples)
        use_fp16 = getattr(getattr(model, "device", None), "type", "cpu") == "cuda"
        result = model.transcribe(
            samples,
            language=None if language in (None, "", "auto") else language,
            task="transcribe",
            fp16=use_fp16,
            condition_on_previous_text=False,
            verbose=None,
        )
    except ModelLoadError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Whisper inference failed")
        raise TranscriptionError("Speech recognition failed while processing the audio.") from exc

    segments = [
        {"start": float(s.get("start", 0.0)), "end": float(s.get("end", 0.0)), "text": (s.get("text") or "").strip()}
        for s in result.get("segments", [])
    ]
    return {
        "text": (result.get("text") or "").strip(),
        "language": result.get("language") or (language if language not in (None, "auto") else "unknown"),
        "segments": segments,
    }


def transcribe_audio_chunks(chunks, model_name="base", language=None, device_preference="auto",
                            progress_callback=None):
    """Transcribe a list of {"path", "start", "end"} chunks and merge the output.

    The language is detected on the first chunk (when not chosen by the user)
    and reused for the remaining chunks so the whole recording is consistent.
    """
    if not chunks:
        raise TranscriptionError("There is no audio to transcribe.")
    chosen = None if language in (None, "", "auto") else language
    texts, segments, detected = [], [], chosen
    for position, chunk in enumerate(chunks, 1):
        part = transcribe_audio(chunk["path"], model_name, chosen or detected, device_preference)
        if detected is None:
            detected = part["language"]
        texts.append(part["text"])
        offset = float(chunk.get("start", 0.0))
        for seg in part["segments"]:
            segments.append({"start": seg["start"] + offset, "end": seg["end"] + offset, "text": seg["text"]})
        if progress_callback:
            progress_callback(position, len(chunks))
    return {"text": join_transcripts(texts), "language": detected or "unknown", "segments": segments}
