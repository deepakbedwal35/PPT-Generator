import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deck_maker import config


class ConfigTests(unittest.TestCase):
    def test_constants(self):
        self.assertTrue(config.ROOT.is_dir())
        self.assertTrue(config.PUBLIC.is_dir())
        self.assertEqual(config.MAX_PDF, 15 * 1024 * 1024)
        self.assertEqual(config.MAX_SLIDES, 30)
        self.assertIn("presentationml", config.PPTX_TYPE)

    def test_load_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("TEST_DECK_VAR=sample_value\n# Comment\nINVALID_LINE\n")
            with patch.dict(os.environ, {}, clear=False):
                if "TEST_DECK_VAR" in os.environ:
                    del os.environ["TEST_DECK_VAR"]
                config.load_environment(env_file)
                self.assertEqual(os.environ.get("TEST_DECK_VAR"), "sample_value")

    def test_executable_path_explicit(self):
        with tempfile.NamedTemporaryFile() as tmp:
            with patch.dict(os.environ, {"CUSTOM_TOOL": tmp.name}):
                self.assertEqual(config.executable_path("CUSTOM_TOOL", "nonexistent_cmd"), tmp.name)

    def test_executable_path_missing(self):
        with patch.dict(os.environ, {"CUSTOM_TOOL": ""}):
            self.assertIsNone(config.executable_path("CUSTOM_TOOL", "totally_nonexistent_executable_12345"))

    def test_settings_structure(self):
        s = config.settings()
        self.assertIn("generate", s)
        self.assertIn("compile", s)
        self.assertIn("render", s)
        self.assertIn("model", s)
        self.assertIn("clsi", s)


if __name__ == "__main__":
    unittest.main()
