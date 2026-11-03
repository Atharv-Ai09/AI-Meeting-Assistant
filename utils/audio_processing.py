"""Audio validation, conversion, normalisation and chunking.

Everything the speech model receives is first converted by FFmpeg to
16 kHz, mono, 16-bit PCM WAV, which is the format Whisper expects.
"""
import logging
import os
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from utils.file_utils import get_extension

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000
DEFAULT_ALLOWED_EXTENSIONS = frozenset({"wav", "mp3", "m4a", "flac", "ogg", "webm"})
FFMPEG_TIMEOUT_SECONDS = 1800


class AudioProcessingError(Exception):
    """Raised when audio cannot be processed. Messages are safe to show to users."""


class AudioValidationError(AudioProcessingError):
    """Raised when an audio file fails validation."""


class FFmpegNotFoundError(AudioProcessingError):
    """Raised when the FFmpeg executables are not installed."""


def _ffmpeg_bin():
    return os.getenv("FFMPEG_BINARY", "ffmpeg")


def _ffprobe_bin():
    return os.getenv("FFPROBE_BINARY", "ffprobe")


def ffmpeg_available():
    """True when both ffmpeg and ffprobe can be found."""
    return bool(shutil.which(_ffmpeg_bin()) and shutil.which(_ffprobe_bin()))


def _run(command):
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FFmpegNotFoundError(
            "FFmpeg is not installed or not on PATH. Install FFmpeg and restart the application."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioProcessingError("Audio processing timed out. Try a shorter recording.") from exc


def validate_audio(file_path, original_filename=None, allowed_extensions=None, max_size_bytes=None):
    """Validate an audio file; raises AudioValidationError when it is not usable.

    Checks the extension, existence, size (non-empty and within the limit) and
    asks FFprobe to confirm that the file contains a decodable audio stream.
    """
    allowed = allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS
    path = Path(file_path)
    name = original_filename or path.name
    extension = get_extension(name)

    if extension not in allowed:
        shown = f".{extension}" if extension else "(no extension)"
        raise AudioValidationError(
            f"Unsupported audio format {shown}. Allowed formats: "
            + ", ".join(sorted(e.upper() for e in allowed))
            + "."
        )
    if not path.is_file():
        raise AudioValidationError("The audio file was not received. Please upload it again.")

    size = path.stat().st_size
    if size == 0:
        raise AudioValidationError("The uploaded audio file is empty.")
    if max_size_bytes and size > max_size_bytes:
        raise AudioValidationError(
            f"The audio file is too large. Maximum allowed size is {max_size_bytes // (1024 * 1024)} MB."
        )

    result = _run(
        [
            _ffprobe_bin(), "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path),
        ]
    )
    if result.returncode != 0 or "audio" not in (result.stdout or ""):
        logger.info("ffprobe rejected an upload: %s", (result.stderr or "").strip()[:200])
        raise AudioValidationError(
            "The file is corrupted or does not contain readable audio."
        )
    return True


def _wav_duration(path):
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        if rate <= 0:
            raise wave.Error("invalid sample rate")
        return handle.getnframes() / float(rate)


def get_audio_duration(file_path):
    """Return the duration of an audio file in seconds."""
    path = Path(file_path)
    if path.suffix.lower() == ".wav":
        try:
            return _wav_duration(path)
        except (wave.Error, EOFError):
            pass

    result = _run(
        [_ffprobe_bin(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    )
    if result.returncode == 0:
        try:
            value = float((result.stdout or "").strip().splitlines()[0])
            if value > 0:
                return value
        except (ValueError, IndexError):
            pass

    try:  # optional fallback
        import librosa

        value = float(librosa.get_duration(path=str(path)))
        if value > 0:
            return value
    except Exception:  # noqa: BLE001 - any failure means "unknown"
        pass
    raise AudioProcessingError("Could not determine the audio duration.")


def _convert_with_pydub(input_path, output_path):
    """Fallback converter used only when the direct FFmpeg call fails."""
    from pydub import AudioSegment

    segment = AudioSegment.from_file(str(input_path))
    segment = segment.set_channels(1).set_frame_rate(TARGET_SAMPLE_RATE).set_sample_width(2)
    segment.export(str(output_path), format="wav")


def convert_audio(input_path, output_dir, output_name="converted.wav"):
    """Convert any FFmpeg-readable audio to 16 kHz mono 16-bit WAV."""
    output_path = Path(output_dir) / output_name
    result = _run(
        [
            _ffmpeg_bin(), "-y", "-v", "error", "-i", str(input_path), "-vn",
            "-ac", "1", "-ar", str(TARGET_SAMPLE_RATE), "-c:a", "pcm_s16le",
            "-f", "wav", str(output_path),
        ]
    )
    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size <= 44:
        logger.warning("FFmpeg conversion failed: %s", (result.stderr or "").strip()[:300])
        try:
            _convert_with_pydub(input_path, output_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("pydub fallback failed: %s", type(exc).__name__)
            raise AudioProcessingError(
                "The audio could not be decoded. The file may be corrupted."
            ) from exc

    try:
        with wave.open(str(output_path), "rb") as handle:
            if handle.getnframes() == 0:
                raise AudioValidationError("The audio file contains no audio data.")
    except (wave.Error, EOFError) as exc:
        raise AudioProcessingError("The audio could not be converted to WAV.") from exc
    return output_path


def load_audio_array(wav_path):
    """Load a 16 kHz mono WAV file as a float32 array in the range [-1, 1]."""
    try:
        import soundfile as sf

        data, rate = sf.read(str(wav_path), dtype="float32", always_2d=False)
        if rate == TARGET_SAMPLE_RATE and data.ndim == 1:
            return data
    except Exception:  # noqa: BLE001 - fall back to the standard library
        pass

    with wave.open(str(wav_path), "rb") as handle:
        if handle.getsampwidth() != 2 or handle.getnchannels() != 1:
            raise AudioProcessingError("Audio must be 16-bit mono WAV before analysis.")
        frames = handle.readframes(handle.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def normalize_audio(samples, target_peak=0.95, max_gain=10.0):
    """Peak-normalise a float audio array (gain is capped to avoid boosting noise)."""
    array = np.asarray(samples, dtype=np.float32)
    if array.size == 0:
        raise AudioProcessingError("Cannot normalise empty audio.")
    peak = float(np.max(np.abs(array)))
    if peak < 1e-8:
        return array
    gain = min(target_peak / peak, max_gain)
    return np.clip(array * gain, -1.0, 1.0).astype(np.float32)


def _write_wav(path, pcm_bytes, rate=TARGET_SAMPLE_RATE):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm_bytes)


def _quiet_boundary(handle, target, window_frames, lower_bound, rate):
    """Pick the quietest 0.1 s frame shortly before `target` so words are not cut."""
    begin = max(lower_bound, target - window_frames)
    if target - begin < rate // 5:
        return target
    handle.setpos(begin)
    block = np.frombuffer(handle.readframes(target - begin), dtype=np.int16).astype(np.float32)
    frame = max(1, rate // 10)
    count = len(block) // frame
    if count < 2:
        return target
    energy = np.sqrt(np.mean(block[: count * frame].reshape(count, frame) ** 2, axis=1))
    quietest = int(np.argmin(energy))
    return min(target, begin + quietest * frame + frame // 2)


def split_audio_into_chunks(wav_path, output_dir, chunk_seconds=300, search_seconds=10.0):
    """Split a 16 kHz mono WAV into chunks, preferring to cut at quiet moments.

    Returns a list of dicts: {"path", "start", "end"} (times in seconds).
    """
    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be positive.")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        handle = wave.open(str(wav_path), "rb")
    except (wave.Error, EOFError) as exc:
        raise AudioProcessingError("The converted audio could not be read.") from exc

    chunks = []
    with handle:
        rate, channels, width, total = (
            handle.getframerate(), handle.getnchannels(), handle.getsampwidth(), handle.getnframes(),
        )
        if channels != 1 or width != 2:
            raise AudioProcessingError("Audio must be converted to 16-bit mono WAV before splitting.")
        if total == 0:
            raise AudioValidationError("The audio file contains no audio data.")

        chunk_frames = max(int(chunk_seconds * rate), rate)
        window = int(search_seconds * rate)
        start, index = 0, 0
        while start < total:
            end = min(start + chunk_frames, total)
            if end < total:
                end = _quiet_boundary(handle, end, window, start + rate, rate)
            handle.setpos(start)
            data = handle.readframes(end - start)
            chunk_path = output_dir / f"chunk_{index:04d}.wav"
            _write_wav(chunk_path, data, rate)
            chunks.append({"path": chunk_path, "start": start / rate, "end": end / rate})
            start, index = end, index + 1
    return chunks
