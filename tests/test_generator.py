import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from deck_maker import generator
from deck_maker.exceptions import AppError


class GeneratorTests(unittest.TestCase):
    def test_count_frames(self):
        tex = r"""
        \documentclass{beamer}
        \begin{document}
        % \begin{frame}{Commented}
        \begin{frame}{First}Content\end{frame}
        \begin{frame}{Second}Content\end{frame}
        \end{document}
        """
        self.assertEqual(generator.count_frames(tex), 2)

    def test_input_validation(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            # Empty / invalid brief
            for bad_brief in ("", "   ", None, 123, "a" * 4001):
                with self.assertRaises(AppError):
                    generator.generate_latex(bad_brief, 3)
            # Invalid slide counts
            for bad_count in (2, 13, 0, "5", None):
                with self.assertRaises(AppError):
                    generator.generate_latex("Valid brief", bad_count)

    def test_missing_api_key(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaisesRegex(AppError, "Set GEMINI_API_KEY"):
                generator.generate_latex_once("Valid brief", 4)

    def test_frame_count_retry_success(self):
        good_sample = (generator.beamer_source(
            r"\documentclass{beamer}\begin{document}"
            r"\begin{frame}{1}\end{frame}"
            r"\begin{frame}{2}\end{frame}"
            r"\begin{frame}{3}\end{frame}"
            r"\end{document}"
        ))
        bad_sample = (generator.beamer_source(
            r"\documentclass{beamer}\begin{document}"
            r"\begin{frame}{1}\end{frame}"
            r"\begin{frame}{2}\end{frame}"
            r"\end{document}"
        ))
        mock_fn = MagicMock(side_effect=[bad_sample, good_sample])
        result = generator.generate_latex("Brief", 3, generate_fn=mock_fn)
        self.assertEqual(result, good_sample)
        self.assertEqual(mock_fn.call_count, 2)

    def test_frame_count_retry_failure(self):
        bad_sample = (generator.beamer_source(
            r"\documentclass{beamer}\begin{document}"
            r"\begin{frame}{1}\end{frame}"
            r"\end{document}"
        ))
        mock_fn = MagicMock(return_value=bad_sample)
        with self.assertRaisesRegex(AppError, "returned 1 frames instead of 3"):
            generator.generate_latex("Brief", 3, generate_fn=mock_fn)


if __name__ == "__main__":
    unittest.main()
