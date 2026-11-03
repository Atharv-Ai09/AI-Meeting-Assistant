"""Application entry point: Speech Recognition and Meeting Summarization Using AI.

Run with:  python app.py
"""
import logging
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from config import Config

logger = logging.getLogger(__name__)


def _configure_logging(level_name):
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=getattr(logging, level_name, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )


def create_app(test_config=None):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
        if "MAX_UPLOAD_MB" in test_config and "MAX_CONTENT_LENGTH" not in test_config:
            app.config["MAX_CONTENT_LENGTH"] = test_config["MAX_UPLOAD_MB"] * 1024 * 1024

    _configure_logging(app.config["LOG_LEVEL"])
    for key in ("UPLOAD_FOLDER", "EXPORT_FOLDER"):
        Path(app.config[key]).mkdir(parents=True, exist_ok=True)

    from backend.routes import bp
    app.register_blueprint(bp)
    _register_error_handlers(app)
    return app


def _wants_json():
    return request.path.startswith(("/api/", "/download/", "/health"))


def _register_error_handlers(app):
    messages = {
        400: "Bad request.",
        404: "The requested resource was not found.",
        405: "This method is not allowed for the requested URL.",
        413: None,
    }

    @app.errorhandler(HTTPException)
    def handle_http(exc):
        code = exc.code or 500
        message = messages.get(code, exc.name)
        if code == 413:
            message = f"The file is too large. Maximum upload size is {app.config['MAX_UPLOAD_MB']} MB."
        if _wants_json():
            return jsonify({"success": False, "error": message}), code
        return render_template("error.html", code=code, message=message), code

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        logger.exception("Unhandled exception")
        message = "An unexpected server error occurred."
        if _wants_json():
            return jsonify({"success": False, "error": message}), 500
        return render_template("error.html", code=500, message=message), 500


if __name__ == "__main__":
    application = create_app()
    application.run(host=application.config["HOST"], port=application.config["PORT"], debug=application.config["DEBUG"])
