"""End-to-end conversion tests executing real transformations on temporary files."""

import os
import tempfile
import unittest

from fconv.cli import main


SAMPLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100">
  <rect width="200" height="100" fill="#2563eb" rx="10"/>
  <text x="100" y="55" font-family="sans-serif" font-size="20" fill="#ffffff" text-anchor="middle">Test SVG</text>
</svg>"""

SAMPLE_MD = """# Sample Document

This is an automated conversion test.

- Point A
- Point B

| Col 1 | Col 2 |
| ----- | ----- |
| Val 1 | Val 2 |
"""


class TestEndToEndConversions(unittest.TestCase):
    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory(prefix="fconv_e2e_")
        self.temp_dir = self.temp_dir_obj.name

        self.svg_file = os.path.join(self.temp_dir, "test.svg")
        with open(self.svg_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_SVG)

        self.md_file = os.path.join(self.temp_dir, "test.md")
        with open(self.md_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_MD)

    def tearDown(self):
        self.temp_dir_obj.cleanup()

    def test_svg_to_pdf(self):
        pdf_out = os.path.join(self.temp_dir, "output.pdf")
        ret = main([self.svg_file, pdf_out])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(pdf_out))
        self.assertGreater(os.path.getsize(pdf_out), 0)

    def test_svg_to_png_with_dpi(self):
        png_out = os.path.join(self.temp_dir, "output.png")
        ret = main([self.svg_file, png_out, "-dpi=300"])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(png_out))
        self.assertGreater(os.path.getsize(png_out), 0)

    def test_pdf_to_svg_roundtrip(self):
        pdf_out = os.path.join(self.temp_dir, "step1.pdf")
        svg_out = os.path.join(self.temp_dir, "roundtrip.svg")
        self.assertEqual(main([self.svg_file, pdf_out]), 0)
        self.assertEqual(main([pdf_out, svg_out]), 0)
        self.assertTrue(os.path.exists(svg_out))
        self.assertGreater(os.path.getsize(svg_out), 0)

    def test_pdf_to_png(self):
        pdf_out = os.path.join(self.temp_dir, "doc.pdf")
        png_out = os.path.join(self.temp_dir, "doc.png")
        self.assertEqual(main([self.svg_file, pdf_out]), 0)
        self.assertEqual(main([pdf_out, png_out, "--dpi", "200"]), 0)
        self.assertTrue(os.path.exists(png_out))
        self.assertGreater(os.path.getsize(png_out), 0)

    def test_md_to_html(self):
        html_out = os.path.join(self.temp_dir, "doc.html")
        ret = main([self.md_file, html_out])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(html_out))
        with open(html_out, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Sample Document", content)
        self.assertIn("Point A", content)

    def test_md_to_docx(self):
        docx_out = os.path.join(self.temp_dir, "doc.docx")
        ret = main([self.md_file, docx_out])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(docx_out))
        self.assertGreater(os.path.getsize(docx_out), 0)

    def test_png_to_jpg(self):
        png_temp = os.path.join(self.temp_dir, "source.png")
        jpg_out = os.path.join(self.temp_dir, "converted.jpg")
        self.assertEqual(main([self.svg_file, png_temp]), 0)
        ret = main([png_temp, jpg_out, "--quality", "85"])
        self.assertEqual(ret, 0)
        self.assertTrue(os.path.exists(jpg_out))
        self.assertGreater(os.path.getsize(jpg_out), 0)

    def test_png_to_webp_roundtrip(self):
        png_temp = os.path.join(self.temp_dir, "icon.png")
        webp_out = os.path.join(self.temp_dir, "icon.webp")
        png_restored = os.path.join(self.temp_dir, "icon_restored.png")
        self.assertEqual(main([self.svg_file, png_temp]), 0)
        self.assertEqual(main([png_temp, webp_out, "--quality", "80"]), 0)
        self.assertTrue(os.path.exists(webp_out))
        self.assertEqual(main([webp_out, png_restored]), 0)
        self.assertTrue(os.path.exists(png_restored))
        self.assertGreater(os.path.getsize(png_restored), 0)


if __name__ == "__main__":
    unittest.main()
