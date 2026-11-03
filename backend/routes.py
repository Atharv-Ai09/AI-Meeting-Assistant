"""Flask routes: pages and REST API."""
import importlib.util
import logging
from functools import wraps

from werkzeug.exceptions import HTTPException
from flask import (Blueprint, abort, current_app, jsonify, render_template, request,
                   send_from_directory, url_for)

from backend import services
from backend.validators import (ValidationError, validate_audio_upload, validate_language,
                                validate_summary_length, validate_transcript_payload,
                                validate_whisper_model)
from models import speech_model, summarization_model
from models.speech_model import ModelLoadError, NoSpeechDetectedError, TranscriptionError
from models.summarization_model import SummarizationModelError
from utils import audio_processing as ap
from utils import file_utils as fu

logger = logging.getLogger(__name__)
bp = Blueprint("main", __name__)
APP_VERSION = "1.0.0"


def _error(message, status):
    return jsonify({"success": False, "error": message}), status


def api_errors(view):
    """Translate known exceptions to JSON errors without leaking internals."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except ValidationError as exc:
            return _error(exc.message, exc.status_code)
        except ap.FFmpegNotFoundError as exc:
            logger.error("FFmpeg missing")
            return _error(str(exc), 503)
        except ap.AudioProcessingError as exc:  # includes AudioValidationError
            return _error(str(exc), 422)
        except NoSpeechDetectedError as exc:
            return _error(str(exc), 422)
        except (ModelLoadError, SummarizationModelError) as exc:
            return _error(str(exc), 503)
        except TranscriptionError as exc:
            return _error(str(exc), 500)
        except HTTPException:
            raise  # handled by the app-level handlers (e.g. 413 Request Entity Too Large)
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled error in %s", request.path)
            return _error("An unexpected server error occurred. Please try again.", 500)

    return wrapper


def _options():
    cfg = current_app.config
    form = request.form
    return {
        "whisper_model": validate_whisper_model(
            form.get("whisper_model"), cfg["ALLOWED_WHISPER_MODELS"], cfg["DEFAULT_WHISPER_MODEL"]
        ),
        "summary_length": validate_summary_length(
            form.get("summary_length"), cfg["SUMMARY_LENGTHS"], cfg["DEFAULT_SUMMARY_LENGTH"]
        ),
        "language": validate_language(form.get("language"), cfg["SUPPORTED_LANGUAGES"]),
    }


def _downloads(report):
    return {
        kind: url_for("main.download", filename=name)
        for kind, name in (report.get("files") or {}).items()
    }


# ------------------------------------------------------------------ pages
@bp.route("/")
def index():
    cfg = current_app.config
    return render_template(
        "index.html",
        languages=cfg["SUPPORTED_LANGUAGES"],
        whisper_models=cfg["ALLOWED_WHISPER_MODELS"],
        default_model=cfg["DEFAULT_WHISPER_MODEL"],
        max_upload_mb=cfg["MAX_UPLOAD_MB"],
        extensions=sorted(cfg["ALLOWED_AUDIO_EXTENSIONS"]),
    )


@bp.route("/about")
def about():
    cfg = current_app.config
    return render_template(
        "about.html", whisper_models=cfg["ALLOWED_WHISPER_MODELS"], summarizer=cfg["SUMMARIZER_MODEL"]
    )


@bp.route("/result/<report_id>")
def result(report_id):
    report = services.load_report(report_id)
    if report is None:
        abort(404)
    return render_template(
        "result.html", report=report, downloads=_downloads(report),
        summary_lengths=current_app.config["SUMMARY_LENGTHS"],
    )


# ------------------------------------------------------------------ API
@bp.route("/api/transcribe", methods=["POST"])
@api_errors
def api_transcribe():
    safe_name = validate_audio_upload(request.files.get("audio"), current_app.config["ALLOWED_AUDIO_EXTENSIONS"])
    options = _options()
    meta = services.transcribe_upload(request.files["audio"], safe_name, options)
    return jsonify({"success": True, **meta})


@bp.route("/api/summarize", methods=["POST"])
@api_errors
def api_summarize():
    cfg = current_app.config
    payload = request.get_json(silent=True)
    transcript = validate_transcript_payload(payload, cfg["MIN_TRANSCRIPT_WORDS"])
    length = validate_summary_length(payload.get("summary_length"), cfg["SUMMARY_LENGTHS"], cfg["DEFAULT_SUMMARY_LENGTH"])

    report_id = payload.get("report_id")
    if report_id:
        report = services.update_report(report_id, transcript, length) if fu.is_valid_report_id(report_id) else None
        if report is None:
            raise ValidationError("The meeting report was not found. It may have expired.", 404)
        return jsonify({"success": True, "report": report, "downloads": _downloads(report)})

    analysis = services.analyze_transcript(transcript, length, payload.get("language_code"), strict=True)
    return jsonify({"success": True, **analysis})


@bp.route("/api/process", methods=["POST"])
@api_errors
def api_process():
    safe_name = validate_audio_upload(request.files.get("audio"), current_app.config["ALLOWED_AUDIO_EXTENSIONS"])
    options = _options()
    report = services.process_meeting(request.files["audio"], safe_name, options)
    return jsonify({
        "success": True,
        "report": report,
        "result_url": url_for("main.result", report_id=report["id"]),
        "downloads": _downloads(report),
    })


@bp.route("/health")
def health():
    def installed(name):
        return importlib.util.find_spec(name) is not None

    return jsonify({
        "status": "ok",
        "version": APP_VERSION,
        "ffmpeg_available": ap.ffmpeg_available(),
        "packages": {n: installed(n) for n in ("torch", "whisper", "transformers", "librosa", "soundfile", "pydub")},
        "models_loaded": {
            "speech": speech_model.loaded_models(),
            "summarizer": summarization_model.loaded_model_name(),
        },
    })


@bp.route("/download/<filename>")
def download(filename):
    export_dir = current_app.config["EXPORT_FOLDER"]
    try:
        path = fu.safe_export_path(export_dir, filename)
    except ValueError:
        abort(404)
    if not path.is_file():
        abort(404)
    kind = filename.rsplit("_", 1)[1].split(".")[0]
    return send_from_directory(
        export_dir, filename, as_attachment=True, mimetype="text/plain",
        download_name=f"meeting_{kind}.txt",
    )
