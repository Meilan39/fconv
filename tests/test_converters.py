"""Unit tests for converter command builders and Markdown parser."""

import unittest
from fconv.converters import librsvg, markdown, macos_native, poppler
from fconv.options import ConvertOptions


class TestConverters(unittest.TestCase):
    def test_librsvg_commands(self):
        opts = ConvertOptions(dpi=300)
        cmd = librsvg.build_svg_to_png_cmd("input.svg", "output.png", opts)
        self.assertEqual(cmd, ["rsvg-convert", "-f", "png", "-d", "300", "-p", "300", "-o", "output.png", "input.svg"])

        pdf_cmd = librsvg.build_svg_to_pdf_cmd("input.svg", "output.pdf", opts)
        self.assertIn("-f", pdf_cmd)
        self.assertIn("pdf", pdf_cmd)

    def test_poppler_commands(self):
        opts = ConvertOptions(dpi=600, page=2)
        ppm_cmd = poppler.build_pdf_to_png_cmd("doc.pdf", "render.png", opts)
        self.assertEqual(ppm_cmd, ["pdftoppm", "-png", "-r", "600", "-singlefile", "-f", "2", "-l", "2", "doc.pdf", "render"])

        cairo_cmd = poppler.build_pdf_to_svg_cmd("doc.pdf", "vector.svg", opts)
        self.assertEqual(cairo_cmd, ["pdftocairo", "-svg", "-f", "2", "-l", "2", "doc.pdf", "vector.svg"])

    def test_macos_native_commands(self):
        opts = ConvertOptions(quality=85)
        sips_cmd = macos_native.build_sips_cmd("in.png", "out.jpg", "jpeg", opts)
        self.assertEqual(sips_cmd, ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", "in.png", "--out", "out.jpg"])

        tu_cmd = macos_native.build_textutil_cmd("page.html", "doc.docx", "docx", opts)
        self.assertEqual(tu_cmd, ["textutil", "-convert", "docx", "page.html", "-output", "doc.docx"])

    def test_markdown_parser(self):
        md = "# Hello\n\nThis is **bold** and *italic*.\n\n```python\nprint('hi')\n```\n"
        html_out = markdown.parse_markdown_to_html(md)
        self.assertIn("<h1>Hello</h1>", html_out)
        self.assertIn("<strong>bold</strong>", html_out)
        self.assertIn("<em>italic</em>", html_out)
        self.assertIn("<pre><code>print(&#x27;hi&#x27;)</code></pre>", html_out)


if __name__ == "__main__":
    unittest.main()
