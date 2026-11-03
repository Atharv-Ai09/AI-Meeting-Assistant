"""Unit tests for utils.text_utils and file_utils."""
import tempfile
import unittest
from pathlib import Path

from utils import file_utils as fu
from utils import text_utils as tu

SAMPLE = (
    "John will send the budget report by Friday. We decided to go with the cloud vendor for hosting. "
    "Sarah to prepare the slides before 15 March. We need to review the contract next week. "
    "The quarterly numbers look healthy and the team is happy about the progress so far."
)


class CleaningTests(unittest.TestCase):
    def test_clean_text_normalises_whitespace(self):
        self.assertEqual(tu.clean_text("  hello \t  world \r\n\r\n\r\n\r\nbye  "), "hello world\n\nbye")

    def test_sanitize_removes_control_characters(self):
        self.assertEqual(tu.sanitize_text("a\x00b\x07c"), "abc")

    def test_sanitize_handles_none(self):
        self.assertEqual(tu.sanitize_text(None), "")


class TranscriptValidationTests(unittest.TestCase):
    def test_empty_transcript(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            tu.validate_transcript("   \n ")

    def test_none_transcript(self):
        with self.assertRaises(ValueError):
            tu.validate_transcript(None)

    def test_non_string_transcript(self):
        with self.assertRaises(ValueError):
            tu.validate_transcript(123)

    def test_too_short(self):
        with self.assertRaisesRegex(ValueError, "too short"):
            tu.validate_transcript("only three words", min_words=5)

    def test_too_long(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            tu.validate_transcript("word " * (tu.MAX_TRANSCRIPT_CHARS // 4))

    def test_valid_transcript_is_cleaned(self):
        self.assertEqual(tu.validate_transcript("  one two three four five  "), "one two three four five")


class ChunkingTests(unittest.TestCase):
    def test_chunks_respect_word_limit(self):
        text = " ".join(f"Sentence number {i} is here." for i in range(100))
        chunks = tu.chunk_text(text, max_words=50)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.split()), 50)

    def test_no_text_lost(self):
        text = " ".join(f"Sentence number {i} is here." for i in range(40))
        joined = " ".join(tu.chunk_text(text, max_words=30))
        self.assertEqual(joined.split(), text.split())

    def test_short_text_single_chunk(self):
        self.assertEqual(len(tu.chunk_text("Hello there. How are you?", 100)), 1)

    def test_very_long_sentence_is_split(self):
        text = " ".join(["word"] * 500)
        chunks = tu.chunk_text(text, max_words=100)
        self.assertTrue(all(len(c.split()) <= 100 for c in chunks))

    def test_empty_text(self):
        self.assertEqual(tu.chunk_text("", 50), [])

    def test_invalid_max_words(self):
        with self.assertRaises(ValueError):
            tu.chunk_text("abc", 0)

    def test_overlap(self):
        text = " ".join(f"Sentence {i} has a few words." for i in range(20))
        chunks = tu.chunk_text(text, max_words=20, overlap_sentences=1)
        self.assertGreater(len(chunks), 2)


class ExtractionTests(unittest.TestCase):
    def test_action_item_with_person_and_deadline(self):
        items = tu.extract_action_items("John will send the budget report by Friday.")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["responsible"], "John")
        self.assertEqual(items[0]["deadline"].lower(), "by friday")

    def test_missing_person_and_deadline_are_not_specified(self):
        items = tu.extract_action_items("We need to review the contract soon enough.")
        self.assertEqual(items[0]["responsible"], tu.NOT_SPECIFIED)
        self.assertEqual(items[0]["deadline"], tu.NOT_SPECIFIED)

    def test_pronoun_is_not_a_person(self):
        items = tu.extract_action_items("I will send the notes tomorrow morning.")
        self.assertEqual(items[0]["responsible"], tu.NOT_SPECIFIED)

    def test_direct_request_names_person(self):
        items = tu.extract_action_items("Priya, can you update the roadmap by end of the week?")
        self.assertEqual(items[0]["responsible"], "Priya")

    def test_no_action_items(self):
        self.assertEqual(tu.extract_action_items("The weather was lovely and everyone enjoyed lunch together."), [])

    def test_tasks_are_verbatim_transcript_sentences(self):
        for item in tu.extract_action_items(SAMPLE):
            self.assertIn(item["task"], SAMPLE)

    def test_decisions(self):
        decisions = tu.extract_decisions(SAMPLE)
        self.assertEqual(decisions, ["We decided to go with the cloud vendor for hosting."])

    def test_undecided_not_reported(self):
        self.assertEqual(tu.extract_decisions("We still need to decide on the vendor next month."), [])

    def test_key_points_come_from_transcript(self):
        for point in tu.extract_key_points(SAMPLE):
            self.assertIn(point, SAMPLE)

    def test_key_points_empty_text(self):
        self.assertEqual(tu.extract_key_points(""), [])


class ReportTextTests(unittest.TestCase):
    def test_report_uses_required_placeholders(self):
        report = {"transcript": "hello world", "summary": "S", "key_points": [], "decisions": [], "action_items": []}
        text = tu.build_report_txt(report)
        self.assertIn(tu.NO_ACTION_ITEMS, text)
        self.assertIn("FULL TRANSCRIPT", text)

    def test_action_items_render(self):
        report = {"transcript": "t", "summary": "S", "key_points": [], "decisions": [],
                  "action_items": [{"task": "Do it", "responsible": "Not specified.", "deadline": "by Friday"}]}
        self.assertIn("Deadline: by Friday", tu.build_summary_txt(report))


class FileUtilsTests(unittest.TestCase):
    def test_sanitize_filename_strips_paths(self):
        name = fu.sanitize_filename("../../etc/passwd.wav")
        self.assertNotIn("/", name)
        self.assertNotIn("..", name)

    def test_sanitize_filename_default(self):
        self.assertEqual(fu.sanitize_filename("///"), "audio")

    def test_allowed_file(self):
        self.assertTrue(fu.allowed_file("a.MP3", {"mp3"}))
        self.assertFalse(fu.allowed_file("a.exe", {"mp3"}))
        self.assertFalse(fu.allowed_file("noext", {"mp3"}))

    def test_safe_export_path_blocks_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("../app.py", "..\\app.py", "abc.txt", "a" * 32 + "_other.txt", ""):
                with self.assertRaises(ValueError):
                    fu.safe_export_path(tmp, bad)
            good = "a" * 32 + "_report.txt"
            self.assertEqual(fu.safe_export_path(tmp, good).parent, Path(tmp).resolve())

    def test_format_duration(self):
        self.assertEqual(fu.format_duration(65), "1:05")
        self.assertEqual(fu.format_duration(3725), "1:02:05")

    def test_cleanup_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "x"
            target.mkdir()
            (target / "f.txt").write_text("1")
            fu.cleanup_path(target)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
