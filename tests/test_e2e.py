"""End-to-end conversion tests executing real transformations on temporary files."""

import os
import sys
import tempfile
import unittest

from fconv.cli import main
from fconv.converters import browser, imagemagick, inkscape, librsvg, macos_native, pandoc, poppler, webp


SAMPLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100">
  <rect width="200" height="100" fill="#2563eb" rx="10"/>
  <text x="100" y="55" font-family="sans-serif" font-size="20" fill="#ffffff" text-anchor="middle">Test SVG</text>
</svg>"""

SAMPLE_MD = """# Heavy Math & Markdown Test

Inline math: $E = mc^2$ and backslash \\(a^2 + b^2 = c^2\\) and var_name_1.

Display math:
$$
\\begin{aligned}
f(x) &= \\mathbb{R} \\to \\mathbb{C} \\\\
\\sum_{i=1}^{n} i &= \\frac{n(n+1)}{2}
\\end{aligned}
$$

Currency costs $5 to $10. Strikethrough ~~old~~ and task list:
- [x] done
- [ ] todo

| Col 1 | Col 2 |
| ----- | ----- |
| $x_1$ | $y_1$ |
"""


def _read_magic(path: str, n: int = 16) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


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

    @unittest.skipUnless(librsvg.has_rsvg_convert() or inkscape.has_inkscape(), "Requires rsvg-convert or inkscape")
    def test_svg_to_pdf(self):
        pdf_out = os.path.join(self.temp_dir, "output.pdf")
        ret = main([self.svg_file, pdf_out])
        self.assertEqual(ret, 0)
        self.assertTrue(_read_magic(pdf_out).startswith(b"%PDF-"))

    @unittest.skipUnless(
        librsvg.has_rsvg_convert() or inkscape.has_inkscape() or imagemagick.has_magick(),
        "Requires SVG rasterizer",
    )
    def test_svg_to_png_with_dpi(self):
        png_out = os.path.join(self.temp_dir, "output.png")
        ret = main([self.svg_file, png_out, "-dpi=300"])
        self.assertEqual(ret, 0)
        self.assertTrue(_read_magic(png_out).startswith(b"\x89PNG\r\n\x1a\n"))

    @unittest.skipUnless(
        (librsvg.has_rsvg_convert() or inkscape.has_inkscape()) and (poppler.has_pdftocairo() or inkscape.has_inkscape()),
        "Requires SVG->PDF and PDF->SVG tools",
    )
    def test_pdf_to_svg_roundtrip(self):
        pdf_out = os.path.join(self.temp_dir, "step1.pdf")
        svg_out = os.path.join(self.temp_dir, "roundtrip.svg")
        self.assertEqual(main([self.svg_file, pdf_out]), 0)
        self.assertEqual(main([pdf_out, svg_out]), 0)
        with open(svg_out, "r", encoding="utf-8") as f:
            self.assertIn("<svg", f.read())

    @unittest.skipUnless(
        (librsvg.has_rsvg_convert() or inkscape.has_inkscape()) and poppler.has_pdftoppm(),
        "Requires SVG->PDF and pdftoppm",
    )
    def test_pdf_to_png(self):
        pdf_out = os.path.join(self.temp_dir, "doc.pdf")
        png_out = os.path.join(self.temp_dir, "doc.png")
        self.assertEqual(main([self.svg_file, pdf_out]), 0)
        self.assertEqual(main([pdf_out, png_out, "--dpi", "200"]), 0)
        self.assertTrue(_read_magic(png_out).startswith(b"\x89PNG\r\n\x1a\n"))

    @unittest.skipUnless(
        (librsvg.has_rsvg_convert() or inkscape.has_inkscape()) and poppler.has_pdftotext(),
        "Requires SVG->PDF and pdftotext",
    )
    def test_pdf_to_txt(self):
        pdf_out = os.path.join(self.temp_dir, "doc.pdf")
        txt_out = os.path.join(self.temp_dir, "doc.txt")
        self.assertEqual(main([self.svg_file, pdf_out]), 0)
        self.assertEqual(main([pdf_out, txt_out]), 0)
        self.assertTrue(os.path.isfile(txt_out))

    def test_md_to_html(self):
        html_out = os.path.join(self.temp_dir, "doc.html")
        ret = main([self.md_file, html_out])
        self.assertEqual(ret, 0)
        with open(html_out, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Heavy Math", content)
        self.assertIn("var_name_1", content)

    @unittest.skipUnless(browser.has_browser(), "Requires headless browser (Chrome/Chromium/Brave)")
    def test_md_to_pdf_default_and_builtin(self):
        pdf_out = os.path.join(self.temp_dir, "heavy.pdf")
        self.assertEqual(main([self.md_file, pdf_out]), 0)
        self.assertTrue(_read_magic(pdf_out).startswith(b"%PDF-"))

        pdf_builtin = os.path.join(self.temp_dir, "heavy_builtin.pdf")
        self.assertEqual(main([self.md_file, pdf_builtin, "--engine", "builtin_md"]), 0)
        self.assertTrue(_read_magic(pdf_builtin).startswith(b"%PDF-"))

    @unittest.skipUnless(pandoc.has_pandoc(), "Requires pandoc for sandbox-safe md->docx")
    def test_md_to_docx(self):
        docx_out = os.path.join(self.temp_dir, "doc.docx")
        ret = main([self.md_file, docx_out])
        self.assertEqual(ret, 0)
        self.assertTrue(_read_magic(docx_out).startswith(b"PK\x03\x04"))

    @unittest.skipUnless(
        (librsvg.has_rsvg_convert() or inkscape.has_inkscape()) and (macos_native.has_sips() or imagemagick.has_magick()),
        "Requires SVG->PNG and sips or magick",
    )
    def test_png_to_jpg_and_pdf(self):
        png_temp = os.path.join(self.temp_dir, "source.png")
        jpg_out = os.path.join(self.temp_dir, "converted.jpg")
        pdf_out = os.path.join(self.temp_dir, "wrapped.pdf")
        self.assertEqual(main([self.svg_file, png_temp]), 0)
        self.assertEqual(main([png_temp, jpg_out, "--quality", "85"]), 0)
        self.assertTrue(_read_magic(jpg_out).startswith(b"\xff\xd8\xff"))
        self.assertEqual(main([png_temp, pdf_out]), 0)
        self.assertTrue(_read_magic(pdf_out).startswith(b"%PDF-"))

    @unittest.skipUnless(
        (librsvg.has_rsvg_convert() or inkscape.has_inkscape())
        and (webp.has_cwebp() or imagemagick.has_magick())
        and (webp.has_dwebp() or (sys.platform == "darwin" and macos_native.has_sips()) or imagemagick.has_magick()),
        "Requires WebP conversion tools",
    )
    def test_png_webp_jpg_roundtrip(self):
        png_temp = os.path.join(self.temp_dir, "icon.png")
        webp_out = os.path.join(self.temp_dir, "icon.webp")
        png_restored = os.path.join(self.temp_dir, "icon_restored.png")
        jpg_from_webp = os.path.join(self.temp_dir, "icon_from_webp.jpg")
        self.assertEqual(main([self.svg_file, png_temp]), 0)
        self.assertEqual(main([png_temp, webp_out, "--quality", "80"]), 0)
        magic_webp = _read_magic(webp_out, 12)
        self.assertEqual(magic_webp[:4], b"RIFF")
        self.assertEqual(magic_webp[8:12], b"WEBP")

        self.assertEqual(main([webp_out, png_restored]), 0)
        self.assertTrue(_read_magic(png_restored).startswith(b"\x89PNG\r\n\x1a\n"))

        if macos_native.has_sips() or imagemagick.has_magick():
            self.assertEqual(main([webp_out, jpg_from_webp]), 0)
            self.assertTrue(_read_magic(jpg_from_webp).startswith(b"\xff\xd8\xff"))


if __name__ == "__main__":
    unittest.main()
