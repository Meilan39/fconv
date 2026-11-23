"""Unit tests for converter command builders and Markdown parser."""

import os
import tempfile
import unittest
from unittest.mock import patch
from fconv.converters import (
    browser,
    imagemagick,
    inkscape,
    librsvg,
    macos_native,
    markdown,
    ocr,
    pandoc,
    poppler,
    webp,
)
from fconv.options import ConvertOptions


class TestConverters(unittest.TestCase):
    def test_librsvg_commands(self):
        opts = ConvertOptions(dpi=300)
        cmd = librsvg.build_svg_to_png_cmd("input.svg", "output.png", opts)
        self.assertEqual(cmd, ["rsvg-convert", "-f", "png", "-d", "300", "-p", "300", "-o", "output.png", "input.svg"])

        pdf_cmd = librsvg.build_svg_to_pdf_cmd("input.svg", "output.pdf", opts)
        self.assertEqual(pdf_cmd, ["rsvg-convert", "-f", "pdf", "-d", "300", "-p", "300", "-o", "output.pdf", "input.svg"])

    def test_poppler_commands(self):
        opts = ConvertOptions(dpi=600, quality=88, page=2)
        ppm_cmd = poppler.build_pdf_to_png_cmd("doc.pdf", "render.png", opts)
        self.assertEqual(ppm_cmd, ["pdftoppm", "-png", "-r", "600", "-singlefile", "-f", "2", "-l", "2", "doc.pdf", "render"])

        jpg_cmd = poppler.build_pdf_to_jpg_cmd("doc.pdf", "render.jpeg", opts)
        self.assertEqual(
            jpg_cmd,
            ["pdftoppm", "-jpeg", "-r", "600", "-singlefile", "-jpegopt", "quality=88", "-f", "2", "-l", "2", "doc.pdf", "render"],
        )

        tiff_cmd = poppler.build_pdf_to_tiff_cmd("doc.pdf", "render.tiff", opts)
        self.assertEqual(tiff_cmd, ["pdftoppm", "-tiff", "-r", "600", "-singlefile", "-f", "2", "-l", "2", "doc.pdf", "render"])

        cairo_cmd = poppler.build_pdf_to_svg_cmd("doc.pdf", "vector.svg", opts)
        self.assertEqual(cairo_cmd, ["pdftocairo", "-svg", "-f", "2", "-l", "2", "doc.pdf", "vector.svg"])

        cairo_default = poppler.build_pdf_to_svg_cmd("doc.pdf", "vector.svg", ConvertOptions())
        self.assertEqual(cairo_default, ["pdftocairo", "-svg", "-f", "1", "-l", "1", "doc.pdf", "vector.svg"])

        txt_cmd = poppler.build_pdf_to_txt_cmd("doc.pdf", "doc.txt", opts)
        self.assertEqual(txt_cmd, ["pdftotext", "-layout", "-f", "2", "-l", "2", "doc.pdf", "doc.txt"])

    def test_inkscape_commands(self):
        self.assertEqual(
            inkscape.build_pdf_to_svg_inkscape_cmd("a.pdf", "a.svg", ConvertOptions(page=3)),
            ["inkscape", "--pdf-poppler", "--pages=3", "-o", "a.svg", "a.pdf"],
        )
        self.assertEqual(
            inkscape.build_svg_to_pdf_inkscape_cmd("a.svg", "a.pdf", ConvertOptions()),
            ["inkscape", "-o", "a.pdf", "a.svg"],
        )
        self.assertEqual(
            inkscape.build_svg_to_png_inkscape_cmd("a.svg", "a.png", ConvertOptions()),
            ["inkscape", "-o", "a.png", "-d", "300", "a.svg"],
        )

    def test_macos_native_commands_and_platform(self):
        opts = ConvertOptions(quality=85)
        sips_cmd = macos_native.build_sips_cmd("in.png", "out.jpg", "jpeg", opts)
        self.assertEqual(sips_cmd, ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", "in.png", "--out", "out.jpg"])

        tu_cmd = macos_native.build_textutil_cmd("page.html", "doc.docx", "docx", opts)
        self.assertEqual(tu_cmd, ["textutil", "-convert", "docx", "page.html", "-output", "doc.docx"])

        with patch("fconv.converters.macos_native.sys.platform", "linux"):
            self.assertFalse(macos_native.has_sips())
            self.assertFalse(macos_native.has_textutil())

    def test_webp_commands(self):
        self.assertEqual(
            webp.build_cwebp_cmd("a.png", "a.webp", ConvertOptions(quality=75)),
            ["cwebp", "-q", "75", "a.png", "-o", "a.webp"],
        )
        self.assertEqual(
            webp.build_dwebp_cmd("a.webp", "a.png", ConvertOptions(), target_fmt="png"),
            ["dwebp", "a.webp", "-o", "a.png"],
        )
        self.assertEqual(
            webp.build_dwebp_cmd("a.webp", "a.bmp", ConvertOptions(), target_fmt="bmp"),
            ["dwebp", "a.webp", "-bmp", "-o", "a.bmp"],
        )
        self.assertEqual(
            webp.build_dwebp_cmd("a.webp", "a.tiff", ConvertOptions(), target_fmt="tiff"),
            ["dwebp", "a.webp", "-tiff", "-o", "a.tiff"],
        )
        with self.assertRaises(ValueError):
            webp.build_dwebp_cmd("a.webp", "a.jpg", ConvertOptions(), target_fmt="jpg")

    def test_imagemagick_commands(self):
        cmd_pdf = imagemagick.build_magick_cmd(
            "doc.pdf", "out.jpg", ConvertOptions(dpi=200, page=2, quality=90), source_fmt="pdf", target_fmt="jpg"
        )
        self.assertEqual(
            cmd_pdf,
            ["magick", "-density", "200", "doc.pdf[1]", "-background", "white", "-alpha", "remove", "-alpha", "off", "-quality", "90", "out.jpg"],
        )

    def test_browser_command_uri_and_missing_preview(self):
        with patch("fconv.converters.browser.find_browser_binary", return_value=None):
            cmd = browser.build_browser_pdf_cmd("/tmp/my doc#1.html", "/tmp/out.pdf", ConvertOptions(), "/tmp/prof")
        self.assertEqual(cmd[0], "google-chrome")
        self.assertIn("--virtual-time-budget=3000", cmd)
        self.assertTrue(cmd[-1].startswith("file:///"))
        self.assertIn("my%20doc%231.html", cmd[-1])
        self.assertTrue(any(arg.startswith("--print-to-pdf=") and arg.endswith("/tmp/out.pdf") for arg in cmd))

    def test_ocr_commands(self):
        self.assertEqual(
            ocr.build_tesseract_cmd("scan.png", "out.txt", ConvertOptions()),
            ["tesseract", "scan.png", "out", "-l", "eng"],
        )

    def test_markdown_parser_math_currency_snake_case_and_lists(self):
        md = (
            "# Title\n\n"
            "Line one of paragraph\n"
            "Line two of paragraph\n\n"
            "Inline math $x_i + y_j$ and `a_b` and *em* and snake_case_var.\n\n"
            "Costs $5 to $10 or $5-$10.\n\n"
            "\\[\n\\sum_{i=1}^n x_i < y_i\n\\]\n\n"
            "2. Second\n"
            "- [x] Done task\n"
            "- [ ] Todo task\n"
        )
        self.assertTrue(markdown.contains_math(md))
        self.assertFalse(markdown.contains_math("Price is $5 and $10 or $5-$10 and `$x_i$` in code.\n"))

        html_out = markdown.parse_markdown_to_html(md)
        self.assertIn("<p>Line one of paragraph Line two of paragraph</p>", html_out)
        self.assertIn("$x_i + y_j$", html_out)
        self.assertIn("<code>a_b</code>", html_out)
        self.assertIn("<em>em</em>", html_out)
        self.assertIn("snake_case_var", html_out)
        self.assertNotIn("<em>case</em>", html_out)
        self.assertNotIn("<em>i", html_out)
        self.assertIn("Costs $5 to $10 or $5-$10.", html_out)
        self.assertIn('<div class="math-display">\\[\n\\sum_{i=1}^n x_i &lt; y_i\n\\]</div>', html_out)
        self.assertIn('<ol start="2">\n<li>Second</li>\n</ol>', html_out)
        self.assertIn('<input type="checkbox" checked disabled> Done task', html_out)
        self.assertIn('<input type="checkbox" disabled> Todo task', html_out)

        with tempfile.TemporaryDirectory() as tmp:
            plain_html = os.path.join(tmp, "plain.html")
            math_html = os.path.join(tmp, "math.html")
            plain_md = os.path.join(tmp, "plain.md")
            math_md = os.path.join(tmp, "math.md")
            with open(plain_md, "w", encoding="utf-8") as f:
                f.write("# Plain\n\nNo math here.\n")
            with open(math_md, "w", encoding="utf-8") as f:
                f.write(md)

            opts = ConvertOptions()
            markdown.convert_markdown_to_html(plain_md, plain_html, opts)
            markdown.convert_markdown_to_html(math_md, math_html, opts)

            with open(plain_html, "r", encoding="utf-8") as f:
                plain_content = f.read()
            with open(math_html, "r", encoding="utf-8") as f:
                math_content = f.read()

            self.assertIn("<base href=", plain_content)
            self.assertIn("@page", plain_content)
            self.assertIn("margin: 12mm 14mm;", plain_content)
            self.assertNotIn("katex", plain_content)
            self.assertIn("katex", math_content)

    def test_pandoc_commands(self):
        opts = ConvertOptions()
        with patch("fconv.converters.pandoc.find_pdf_engine", return_value="/Library/TeX/texbin/xelatex"), patch(
            "fconv.converters.pandoc._has_tex_package", return_value=False
        ):
            pdf_cmd = pandoc.build_md_to_pdf_pandoc_cmd("/tmp/notes.md", "/tmp/notes.out", opts)
        self.assertIn("--pdf-engine=/Library/TeX/texbin/xelatex", pdf_cmd)
        self.assertIn("-t", pdf_cmd)
        self.assertEqual(pdf_cmd[pdf_cmd.index("-t") + 1], "pdf")
        self.assertIn("-strikeout", pdf_cmd[pdf_cmd.index("-f") + 1])

        html_cmd = pandoc.build_md_to_html_pandoc_cmd("/tmp/notes.md", "/tmp/notes.html", opts, header_file="/tmp/h.html")
        self.assertIn("--math-method=mathml", html_cmd)
        self.assertIn("--standalone", html_cmd)
        self.assertIn("-H", html_cmd)

        doc_cmd = pandoc.build_pandoc_doc_cmd("/tmp/a.docx", "/tmp/a.md", "docx", "md", opts)
        self.assertEqual(doc_cmd, ["pandoc", "/tmp/a.docx", "-f", "docx", "-t", "gfm", "-o", "/tmp/a.md"])


if __name__ == "__main__":
    unittest.main()
