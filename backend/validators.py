"""Request validation helpers."""
from utils.file_utils import allowed_file, get_extension, sanitize_filename
from utils.text_utils import validate_transcript


class ValidationError(Exception):
    """Invalid request. `message` is safe to show to the user."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_summary_length(value, allowed, default="medium"):
    value = (value or default).strip().lower()
    if value not in allowed:
        raise ValidationError("Invalid summary length. Choose: " + ", ".join(allowed) + ".")
    return value


def validate_whisper_model(value, allowed, default="base"):
    value = (value or default).strip().lower()
    if value not in allowed:
        raise ValidationError("Invalid speech model. Choose: " + ", ".join(allowed) + ".")
    return value


def validate_language(value, supported):
    value = (value or "auto").strip().lower()
    if value not in supported:
        raise ValidationError("Unsupported language selection.")
    return value


def validate_audio_upload(file_storage, allowed_extensions):
    """Check that an upload exists and has an allowed extension; returns a safe name."""
    if file_storage is None or not getattr(file_storage, "filename", ""):
        raise ValidationError("No audio file was provided. Upload a file using the 'audio' field.")
    safe_name = sanitize_filename(file_storage.filename)
    if not allowed_file(safe_name, allowed_extensions):
        ext = get_extension(safe_name)
        shown = f".{ext}" if ext else "(no extension)"
        raise ValidationError(
            f"Unsupported audio format {shown}. Allowed formats: "
            + ", ".join(sorted(e.upper() for e in allowed_extensions)) + ".",
            status_code=415,
        )
    return safe_name


def validate_transcript_payload(payload, min_words):
    """Validate a JSON body containing a 'transcript' string; returns cleaned text."""
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be JSON with a 'transcript' field.")
    try:
        return validate_transcript(payload.get("transcript"), min_words=min_words)
    except ValueError as exc:
        raise ValidationError(str(exc), status_code=422) from exc
