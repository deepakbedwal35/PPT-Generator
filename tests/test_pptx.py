import io
import unittest
import zipfile

from deck_maker import pptx_builder
from deck_maker.exceptions import AppError

# Minimal valid 1x1 RGBA PNG
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class PPTXBuilderTests(unittest.TestCase):
    def test_png_dimensions(self):
        w, h = pptx_builder.png_dimensions(TINY_PNG)
        self.assertEqual(w, 1)
        self.assertEqual(h, 1)

    def test_invalid_png_dimensions(self):
        for bad in (b"", b"not a png", b"\x89PNG\r\n\x1a\n" + bytes(16)):
            with self.assertRaises(AppError):
                pptx_builder.png_dimensions(bad)

    def test_content_types(self):
        xml = pptx_builder.content_types(3)
        self.assertIn('PartName="/ppt/slides/slide1.xml"', xml)
        self.assertIn('PartName="/ppt/slides/slide2.xml"', xml)
        self.assertIn('PartName="/ppt/slides/slide3.xml"', xml)

    def test_pptx_from_images(self):
        data = pptx_builder.pptx_from_images([TINY_PNG, TINY_PNG])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIsNone(archive.testzip())
            namelist = archive.namelist()
            self.assertIn("[Content_Types].xml", namelist)
            self.assertIn("ppt/presentation.xml", namelist)
            self.assertIn("ppt/slides/slide1.xml", namelist)
            self.assertIn("ppt/slides/slide2.xml", namelist)
            self.assertIn("ppt/media/image1.png", namelist)
            self.assertIn("ppt/media/image2.png", namelist)

    def test_pptx_page_limits(self):
        with self.assertRaises(AppError):
            pptx_builder.pptx_from_images([])
        with self.assertRaises(AppError):
            pptx_builder.pptx_from_images([TINY_PNG] * 31)


if __name__ == "__main__":
    unittest.main()
