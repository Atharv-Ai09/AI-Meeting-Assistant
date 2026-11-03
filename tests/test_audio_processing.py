"""Unit tests for utils.audio_processing (no AI models required)."""
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from utils import audio_processing as ap

FFMPEG_OK = ap.ffmpeg_available()


def make_wav(path, seconds=2.0, rate=16000, channels=1, freq=440.0, silence=None):
    """Write a sine-wave WAV. `silence` = (start_s, end_s) to blank out a range."""
    t = np.arange(int(seconds * rate)) / rate
    signal = 0.5 * np.sin(2 * np.pi * freq * t)
    if silence:
        signal[int(silence[0] * rate):int(silence[1] * rate)] = 0.0
    pcm = (signal * 32767).astype(np.int16)
    if channels == 2:
        pcm = np.repeat(pcm[:, None], 2, axis=1).reshape(-1)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class ValidateAudioTests(TempDirTestCase):
    def test_rejects_unsupported_extension(self):
        path = self.tmp / "notes.txt"
        path.write_text("hello")
        with self.assertRaises(ap.AudioValidationError):
            ap.validate_audio(path)

    def test_rejects_missing_extension(self):
        path = self.tmp / "audio"
        path.write_bytes(b"1234")
        with self.assertRaises(ap.AudioValidationError):
            ap.validate_audio(path)

    def test_rejects_missing_file(self):
        with self.assertRaises(ap.AudioValidationError):
            ap.validate_audio(self.tmp / "missing.wav")

    def test_rejects_empty_file(self):
        path = self.tmp / "empty.wav"
        path.write_bytes(b"")
        with self.assertRaisesRegex(ap.AudioValidationError, "empty"):
            ap.validate_audio(path)

    def test_rejects_oversized_file(self):
        path = self.tmp / "big.wav"
        make_wav(path, seconds=1)
        with self.assertRaisesRegex(ap.AudioValidationError, "too large"):
            ap.validate_audio(path, max_size_bytes=100)

    @unittest.skipUnless(FFMPEG_OK, "FFmpeg not installed")
    def test_rejects_corrupted_audio(self):
        path = self.tmp / "broken.mp3"
        path.write_bytes(b"this is definitely not an mp3 file" * 20)
        with self.assertRaisesRegex(ap.AudioValidationError, "corrupted"):
            ap.validate_audio(path)

    @unittest.skipUnless(FFMPEG_OK, "FFmpeg not installed")
    def test_accepts_valid_wav(self):
        path = self.tmp / "ok.wav"
        make_wav(path)
        self.assertTrue(ap.validate_audio(path))

    def test_error_messages_do_not_expose_paths(self):
        path = self.tmp / "empty.wav"
        path.write_bytes(b"")
        try:
            ap.validate_audio(path)
        except ap.AudioValidationError as exc:
            self.assertNotIn(str(self.tmp), str(exc))


@unittest.skipUnless(FFMPEG_OK, "FFmpeg not installed")
class ConvertAudioTests(TempDirTestCase):
    def test_converts_stereo_44k_to_mono_16k(self):
        src = self.tmp / "stereo.wav"
        make_wav(src, seconds=2, rate=44100, channels=2)
        out = ap.convert_audio(src, self.tmp, "out.wav")
        with wave.open(str(out), "rb") as handle:
            self.assertEqual(handle.getnchannels(), 1)
            self.assertEqual(handle.getframerate(), 16000)
            self.assertEqual(handle.getsampwidth(), 2)
            self.assertAlmostEqual(handle.getnframes() / 16000, 2.0, delta=0.1)

    def test_corrupted_input_raises(self):
        src = self.tmp / "bad.wav"
        src.write_bytes(b"RIFFnotreallyawavefile" * 10)
        with self.assertRaises(ap.AudioProcessingError):
            ap.convert_audio(src, self.tmp)


class DurationTests(TempDirTestCase):
    def test_wav_duration(self):
        path = self.tmp / "d.wav"
        make_wav(path, seconds=3.5)
        self.assertAlmostEqual(ap.get_audio_duration(path), 3.5, places=2)

    @unittest.skipUnless(FFMPEG_OK, "FFmpeg not installed")
    def test_duration_via_ffprobe_for_corrupt_wav_header_fallback(self):
        path = self.tmp / "d.wav"
        make_wav(path, seconds=1.0)
        self.assertGreater(ap.get_audio_duration(path), 0.9)


class NormalizeTests(unittest.TestCase):
    def test_scales_to_target_peak(self):
        out = ap.normalize_audio(np.array([0.0, 0.1, -0.1], dtype=np.float32), target_peak=0.9)
        self.assertAlmostEqual(float(np.max(np.abs(out))), 0.9, places=5)

    def test_gain_is_capped(self):
        out = ap.normalize_audio(np.array([0.001, -0.001], dtype=np.float32), max_gain=10)
        self.assertAlmostEqual(float(np.max(np.abs(out))), 0.01, places=5)

    def test_silence_unchanged(self):
        out = ap.normalize_audio(np.zeros(100, dtype=np.float32))
        self.assertTrue(np.all(out == 0))

    def test_empty_raises(self):
        with self.assertRaises(ap.AudioProcessingError):
            ap.normalize_audio(np.array([], dtype=np.float32))


class SplitAudioTests(TempDirTestCase):
    def test_splits_and_preserves_all_frames(self):
        src = self.tmp / "long.wav"
        make_wav(src, seconds=25)
        chunks = ap.split_audio_into_chunks(src, self.tmp / "chunks", chunk_seconds=10)
        self.assertGreaterEqual(len(chunks), 3)
        total = 0
        previous_end = 0.0
        for chunk in chunks:
            with wave.open(str(chunk["path"]), "rb") as handle:
                total += handle.getnframes()
            self.assertAlmostEqual(chunk["start"], previous_end, places=3)
            previous_end = chunk["end"]
        self.assertEqual(total, 25 * 16000)

    def test_short_audio_gives_single_chunk(self):
        src = self.tmp / "short.wav"
        make_wav(src, seconds=3)
        chunks = ap.split_audio_into_chunks(src, self.tmp / "c", chunk_seconds=60)
        self.assertEqual(len(chunks), 1)

    def test_cuts_inside_silence(self):
        src = self.tmp / "gap.wav"
        make_wav(src, seconds=25, silence=(8.5, 9.5))
        chunks = ap.split_audio_into_chunks(src, self.tmp / "c", chunk_seconds=10)
        self.assertGreaterEqual(chunks[0]["end"], 8.5)
        self.assertLessEqual(chunks[0]["end"], 9.6)

    def test_invalid_chunk_size(self):
        src = self.tmp / "x.wav"
        make_wav(src, seconds=1)
        with self.assertRaises(ValueError):
            ap.split_audio_into_chunks(src, self.tmp / "c", chunk_seconds=0)

    def test_rejects_stereo_input(self):
        src = self.tmp / "st.wav"
        make_wav(src, seconds=1, channels=2)
        with self.assertRaises(ap.AudioProcessingError):
            ap.split_audio_into_chunks(src, self.tmp / "c")


if __name__ == "__main__":
    unittest.main()
