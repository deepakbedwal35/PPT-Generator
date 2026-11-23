import unittest

from deck_maker import converter
from deck_maker.exceptions import AppError


class ConverterTests(unittest.TestCase):
    def test_ensure_pdf_valid(self):
        pdf = b"%PDF-1.5 minimal sample"
        self.assertEqual(converter.ensure_pdf(pdf), pdf)

    def test_ensure_pdf_invalid(self):
        for bad in (b"", b"NOT_A_PDF", b"\x00\x01\x02"):
            with self.assertRaises(AppError) as ctx:
                converter.ensure_pdf(bad)
            self.assertEqual(ctx.exception.status, 422)

    def test_ensure_pdf_too_large(self):
        large = b"%PDF-" + (b"0" * (15 * 1024 * 1024 + 1))
        with self.assertRaises(AppError) as ctx:
            converter.ensure_pdf(large)
        self.assertEqual(ctx.exception.status, 413)


if __name__ == "__main__":
    unittest.main()
