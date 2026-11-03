"""Flask route tests. AI model inference is mocked; no model downloads are needed."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import create_app
from tests.test_audio_processing import FFMPEG_OK, make_wav
from utils import text_utils as tu

TRANSCRIPT = (
    "John will send the budget report by Friday. We decided to go with the cloud vendor for hosting. "
    "The team discussed the roadmap for the next quarter and agreed on the main priorities. "
    "Sarah to prepare the presentation slides before 15 March. Everyone thanked the clients for their patience."
)


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.app = create_app({
            "TESTING": True,
            "UPLOAD_FOLDER": str(root / "uploads"),
            "EXPORT_FOLDER": str(root / "exports"),
            "MAX_UPLOAD_MB": 1,
        })
        self.client = self.app.test_client()
        self.root = root

    def tearDown(self):
        self._tmp.cleanup()

    def upload(self, url, name="meeting.wav", data=b"RIFF", **form):
        payload = {"audio": (io.BytesIO(data), name)}
        payload.update(form)
        return self.client.post(url, data=payload, content_type="multipart/form-data")


class PageTests(RouteTestCase):
    def test_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("AI Meeting Assistant", body)
        self.assertIn("Transcribe &amp; Summarize", body)
        self.assertIn("Developed by Atharv Shetty", body)

    def test_about_page(self):
        self.assertEqual(self.client.get("/about").status_code, 200)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_all_routes_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        for expected in ("/", "/about", "/api/transcribe", "/api/summarize", "/api/process",
                         "/health", "/download/<filename>", "/result/<report_id>"):
            self.assertIn(expected, rules)

    def test_unknown_page_returns_404_html(self):
        response = self.client.get("/nope")
        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response.content_type)

    def test_unknown_api_returns_json_404(self):
        response = self.client.get("/api/nope")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.get_json()["success"])

    def test_unknown_result_page(self):
        self.assertEqual(self.client.get("/result/" + "a" * 32).status_code, 404)
        self.assertEqual(self.client.get("/result/not-an-id").status_code, 404)


class UploadValidationTests(RouteTestCase):
    def test_no_file(self):
        for url in ("/api/transcribe", "/api/process"):
            response = self.client.post(url, data={}, content_type="multipart/form-data")
            self.assertEqual(response.status_code, 400)
            self.assertIn("error", response.get_json())

    def test_unsupported_extension(self):
        response = self.upload("/api/process", name="virus.exe", data=b"MZ")
        self.assertEqual(response.status_code, 415)

    def test_empty_file(self):
        response = self.upload("/api/transcribe", name="empty.wav", data=b"")
        self.assertEqual(response.status_code, 422)
        self.assertIn("empty", response.get_json()["error"].lower())

    def test_too_large_file(self):
        response = self.upload("/api/process", data=b"0" * (2 * 1024 * 1024))
        self.assertEqual(response.status_code, 413)
        self.assertFalse(response.get_json()["success"])

    @unittest.skipUnless(FFMPEG_OK, "FFmpeg not installed")
    def test_corrupted_file(self):
        response = self.upload("/api/process", name="broken.mp3", data=b"not audio at all" * 30)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(str(self.root), response.get_data(as_text=True))

    def test_invalid_options(self):
        response = self.upload("/api/process", summary_length="huge")
        self.assertEqual(response.status_code, 400)
        response = self.upload("/api/process", whisper_model="large")
        self.assertEqual(response.status_code, 400)
        response = self.upload("/api/process", language="xx")
        self.assertEqual(response.status_code, 400)

    def test_upload_folder_is_cleaned(self):
        self.upload("/api/transcribe", name="empty.wav", data=b"")
        leftovers = [p for p in (self.root / "uploads").iterdir() if p.name != ".gitkeep"]
        self.assertEqual(leftovers, [])


class SummarizeApiTests(RouteTestCase):
    def post_json(self, payload):
        return self.client.post("/api/summarize", json=payload)

    def test_no_json_body(self):
        response = self.client.post("/api/summarize", data="plain", content_type="text/plain")
        self.assertEqual(response.status_code, 400)

    def test_empty_transcript(self):
        response = self.post_json({"transcript": "   "})
        self.assertEqual(response.status_code, 422)
        self.assertIn("empty", response.get_json()["error"].lower())

    def test_missing_transcript_field(self):
        self.assertEqual(self.post_json({}).status_code, 422)

    def test_invalid_length(self):
        self.assertEqual(self.post_json({"transcript": TRANSCRIPT, "summary_length": "x"}).status_code, 400)

    def test_summary_success_with_mocked_model(self):
        with mock.patch("models.summarization_model.summarize_text", return_value="Mock summary.") as fake:
            response = self.post_json({"transcript": TRANSCRIPT, "summary_length": "short"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["summary"], "Mock summary.")
        self.assertEqual(data["action_items"][0]["responsible"], "John")
        self.assertEqual(fake.call_args[0][1], "short")

    def test_short_transcript_skips_model(self):
        with mock.patch("models.summarization_model.summarize_text") as fake:
            response = self.post_json({"transcript": "Short note about the project today."})
        self.assertEqual(response.status_code, 200)
        fake.assert_not_called()
        self.assertTrue(response.get_json()["warnings"])

    def test_no_action_items_returns_empty_list(self):
        with mock.patch("models.summarization_model.summarize_text", return_value="S"):
            response = self.post_json({"transcript": "The weather was lovely and everyone enjoyed lunch together outside today. " * 5})
        self.assertEqual(response.get_json()["action_items"], [])

    def test_model_failure_returns_503_without_trace(self):
        from models.summarization_model import SummarizationModelError
        with mock.patch("models.summarization_model.summarize_text", side_effect=SummarizationModelError("Could not load the summarisation model 'x'.")):
            response = self.post_json({"transcript": TRANSCRIPT})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Traceback", response.get_data(as_text=True))

    def test_unexpected_error_is_hidden(self):
        with mock.patch("models.summarization_model.summarize_text", side_effect=RuntimeError("secret /srv/path")):
            response = self.post_json({"transcript": TRANSCRIPT})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.get_data(as_text=True))


@unittest.skipUnless(FFMPEG_OK, "FFmpeg not installed")
class ProcessWorkflowTests(RouteTestCase):
    def make_audio_bytes(self, seconds=3):
        path = self.root / "in.wav"
        make_wav(path, seconds=seconds)
        return path.read_bytes()

    def run_process(self):
        fake_speech = {"text": TRANSCRIPT, "language": "en", "segments": []}
        with mock.patch("models.speech_model.transcribe_audio_chunks", return_value=fake_speech), \
             mock.patch("models.summarization_model.summarize_text", return_value="Mock summary."):
            return self.upload("/api/process", data=self.make_audio_bytes(), whisper_model="base",
                               summary_length="medium", language="auto")

    def test_full_workflow(self):
        response = self.run_process()
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        report = data["report"]
        self.assertEqual(report["transcript"], TRANSCRIPT)
        self.assertEqual(report["summary"], "Mock summary.")
        self.assertEqual(report["language"], "English")
        self.assertEqual(report["duration_text"], "0:03")
        self.assertTrue(report["decisions"])
        self.assertTrue(data["result_url"].startswith("/result/"))
        leftovers = [p for p in (self.root / "uploads").iterdir() if p.name != ".gitkeep"]
        self.assertEqual(leftovers, [], "temporary files must be removed")

    def test_result_page_and_downloads(self):
        data = self.run_process().get_json()
        page = self.client.get(data["result_url"])
        self.assertEqual(page.status_code, 200)
        body = page.get_data(as_text=True)
        self.assertIn("Process Another Meeting", body)
        self.assertIn("Responsible Person", body)
        for kind in ("transcript", "summary", "report"):
            download = self.client.get(data["downloads"][kind])
            self.assertEqual(download.status_code, 200)
            self.assertIn("attachment", download.headers["Content-Disposition"])
        report_text = self.client.get(data["downloads"]["report"]).get_data(as_text=True)
        self.assertIn("Mock summary.", report_text)
        self.assertIn("FULL TRANSCRIPT", report_text)

    def test_no_speech_detected(self):
        with mock.patch("models.speech_model.transcribe_audio_chunks",
                        return_value={"text": "  ", "language": "en", "segments": []}):
            response = self.upload("/api/process", data=self.make_audio_bytes())
        self.assertEqual(response.status_code, 422)
        self.assertIn("No speech", response.get_json()["error"])

    def test_speech_model_failure(self):
        from models.speech_model import ModelLoadError
        with mock.patch("models.speech_model.transcribe_audio_chunks", side_effect=ModelLoadError("Could not load the Whisper 'base' model.")):
            response = self.upload("/api/process", data=self.make_audio_bytes())
        self.assertEqual(response.status_code, 503)

    def test_summary_failure_keeps_transcript(self):
        from models.summarization_model import SummarizationModelError
        fake_speech = {"text": TRANSCRIPT, "language": "en", "segments": []}
        with mock.patch("models.speech_model.transcribe_audio_chunks", return_value=fake_speech), \
             mock.patch("models.summarization_model.summarize_text", side_effect=SummarizationModelError("offline")):
            response = self.upload("/api/process", data=self.make_audio_bytes())
        self.assertEqual(response.status_code, 200)
        report = response.get_json()["report"]
        self.assertEqual(report["transcript"], TRANSCRIPT)
        self.assertTrue(any("could not be generated" in w for w in report["warnings"]))

    def test_transcribe_endpoint(self):
        fake_speech = {"text": TRANSCRIPT, "language": "en", "segments": []}
        with mock.patch("models.speech_model.transcribe_audio_chunks", return_value=fake_speech):
            response = self.upload("/api/transcribe", data=self.make_audio_bytes())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["transcript"], TRANSCRIPT)

    def test_edit_transcript_regenerates_report(self):
        data = self.run_process().get_json()
        edited = TRANSCRIPT + " Priya will update the website by Monday."
        with mock.patch("models.summarization_model.summarize_text", return_value="Updated summary."):
            response = self.client.post("/api/summarize", json={
                "transcript": edited, "summary_length": "short", "report_id": data["report"]["id"]})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        updated = response.get_json()["report"]
        self.assertEqual(updated["summary"], "Updated summary.")
        self.assertTrue(any(i["responsible"] == "Priya" for i in updated["action_items"]))
        text = self.client.get(data["downloads"]["transcript"]).get_data(as_text=True)
        self.assertIn("Priya will update", text)

    def test_regenerate_unknown_report(self):
        response = self.client.post("/api/summarize", json={"transcript": TRANSCRIPT, "report_id": "b" * 32})
        self.assertEqual(response.status_code, 404)


class DownloadSecurityTests(RouteTestCase):
    def test_traversal_attempts(self):
        for bad in ("..%2f..%2fapp.py", "%2e%2e%2fconfig.py", "..\\app.py", "app.py", "x" * 32 + "_report.txt"):
            self.assertEqual(self.client.get("/download/" + bad).status_code, 404, bad)

    def test_valid_file_download(self):
        name = "c" * 32 + "_summary.txt"
        (self.root / "exports").mkdir(exist_ok=True)
        (self.root / "exports" / name).write_text("hello", encoding="utf-8")
        response = self.client.get("/download/" + name)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "hello")

    def test_json_exports_are_not_downloadable(self):
        (self.root / "exports").mkdir(exist_ok=True)
        (self.root / "exports" / ("d" * 32 + ".json")).write_text("{}")
        self.assertEqual(self.client.get("/download/" + "d" * 32 + ".json").status_code, 404)


if __name__ == "__main__":
    unittest.main()
