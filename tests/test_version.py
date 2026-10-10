import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from logging_setup import LOG_BACKUP_COUNT, LOG_MAX_BYTES
from version import ABOUT_TEXT, VERSION
from help_text import HELP_HTML


class VersionTest(unittest.TestCase):
    def test_version_and_description(self) -> None:
        self.assertEqual(VERSION, "0.2.0")
        self.assertIn("arrivées", ABOUT_TEXT)
        self.assertNotIn("homolog", ABOUT_TEXT.lower())
        self.assertIn("x1", HELP_HTML)
        self.assertIn("Tester caméra", HELP_HTML)
        self.assertIn("Terminer la course", HELP_HTML)

    def test_logs_keep_only_a_few_files(self) -> None:
        self.assertEqual(LOG_BACKUP_COUNT, 2)
        self.assertGreater(LOG_MAX_BYTES, 0)
