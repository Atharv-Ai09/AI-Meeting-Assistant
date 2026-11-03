"""Safe file handling helpers (names, temp folders, exports, cleanup)."""
import json
import logging
import re
import shutil
import tempfile
import time
from pathlib import Path

from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

REPORT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
EXPORT_NAME_RE = re.compile(r"^([0-9a-f]{32})_(transcript|summary|report)\.txt$")


def get_extension(filename):
    """Return the lower-case extension of a filename without the dot."""
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower().strip()


def allowed_file(filename, allowed_extensions):
    """True if the filename has an allowed extension."""
    return get_extension(filename) in allowed_extensions


def sanitize_filename(filename, default="audio"):
    """Return a safe display/storage name (never a path)."""
    name = secure_filename(filename or "")
    return name if name else default


def new_temp_dir(base_dir):
    """Create and return a private temporary working directory."""
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="work_", dir=str(base)))


def cleanup_path(path):
    """Delete a file or directory tree, ignoring errors."""
    if not path:
        return
    target = Path(path)
    try:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()
    except OSError:
        logger.warning("Could not remove temporary item %s", target.name)


def cleanup_old_files(directory, max_age_seconds):
    """Delete files older than max_age_seconds (the .gitkeep file is kept)."""
    directory = Path(directory)
    if not directory.is_dir():
        return 0
    removed = 0
    cutoff = time.time() - max_age_seconds
    for item in directory.iterdir():
        if item.name == ".gitkeep":
            continue
        try:
            if item.stat().st_mtime < cutoff:
                cleanup_path(item)
                removed += 1
        except OSError:
            continue
    return removed


def is_valid_report_id(report_id):
    return isinstance(report_id, str) and bool(REPORT_ID_RE.match(report_id))


def is_valid_export_name(filename):
    return isinstance(filename, str) and bool(EXPORT_NAME_RE.match(filename))


def safe_export_path(export_dir, filename):
    """Resolve an export filename inside export_dir, preventing traversal."""
    if not is_valid_export_name(filename):
        raise ValueError("Invalid file name.")
    base = Path(export_dir).resolve()
    candidate = (base / filename).resolve()
    if candidate.parent != base:
        raise ValueError("Invalid file path.")
    return candidate


def write_text_file(path, text):
    Path(path).write_text(text, encoding="utf-8")


def write_json_file(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json_file(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def format_duration(seconds):
    """Format seconds as M:SS or H:MM:SS."""
    total = max(0, int(round(float(seconds or 0))))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
