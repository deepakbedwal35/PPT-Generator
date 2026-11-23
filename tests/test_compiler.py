from pathlib import Path
import tempfile
import unittest

from deck_maker import compiler
from deck_maker.exceptions import AppError


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.sample = (Path(__file__).resolve().parent.parent / "public" / "sample.tex").read_text()

    def test_beamer_source_cleaning(self):
        clean = compiler.beamer_source(f"```latex\n{self.sample}\n```")
        self.assertEqual(clean, self.sample.strip())

    def test_beamer_source_invalid_types(self):
        for bad in (None, 123, [], {}):
            with self.assertRaises(AppError) as ctx:
                compiler.beamer_source(bad)
            self.assertEqual(ctx.exception.status, 400)

    def test_beamer_source_invalid_documents(self):
        cases = [
            "",
            "   ",
            r"\documentclass{article}\begin{document}Hello\end{document}",
            r"\documentclass{beamer}\begin{center}Hello\end{center}",
        ]
        for bad in cases:
            with self.assertRaises(AppError) as ctx:
                compiler.beamer_source(bad)
            self.assertEqual(ctx.exception.status, 422)

    def test_beamer_source_too_large(self):
        large = r"\documentclass{beamer}\begin{document}" + ("x" * 65536) + r"\end{document}"
        with self.assertRaises(AppError) as ctx:
            compiler.beamer_source(large)
        self.assertEqual(ctx.exception.status, 413)

    def test_compiler_message_extraction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "main.log"
            log_file.write_text("Some prelude\n! Undefined control sequence.\nl.15 \\badcmd\nMore info")
            msg = compiler.compiler_message(log_file, "fallback")
            self.assertIn("Undefined control sequence", msg)

    def test_compiler_message_fallback(self):
        log_file = Path("/nonexistent/path/main.log")
        msg = compiler.compiler_message(log_file, "my fallback error")
        self.assertIn("my fallback error", msg)


if __name__ == "__main__":
    unittest.main()
