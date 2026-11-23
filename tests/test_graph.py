"""Unit tests for format normalization, edge registry, and Dijkstra router."""

import unittest
from unittest.mock import patch
from fconv.graph.edge import Edge, FidelityClass
from fconv.graph.node import SUPPORTED_FORMATS, detect_format_from_path, normalize_format
from fconv.graph.registry import get_default_edges
from fconv.graph.router import Router
from fconv.options import ConvertOptions


class TestGraphRouting(unittest.TestCase):
    def setUp(self):
        self.edges = get_default_edges()
        self.router = Router(self.edges)

    def test_extension_normalization(self):
        self.assertEqual(normalize_format(".svg"), "svg")
        self.assertEqual(normalize_format("jpeg"), "jpg")
        self.assertEqual(normalize_format(".markdown"), "md")
        self.assertEqual(normalize_format("HTML"), "html")
        self.assertEqual(normalize_format(".docx"), "docx")
        self.assertIsNone(normalize_format("svgz"))
        self.assertIsNone(normalize_format("unknown_ext"))

    def test_detect_format_from_path(self):
        self.assertEqual(detect_format_from_path("/path/to/diagram.SVG"), "svg")
        self.assertEqual(detect_format_from_path("photo.jpeg"), "jpg")
        self.assertEqual(detect_format_from_path("README.md"), "md")
        self.assertIsNone(detect_format_from_path("no_extension"))

    def test_registry_invariants(self):
        edge_keys = set()
        used_formats = set()
        opts = ConvertOptions(dpi=300, quality=85, page=1)
        for edge in self.edges:
            self.assertIn(edge.source, SUPPORTED_FORMATS)
            self.assertIn(edge.target, SUPPORTED_FORMATS)
            self.assertGreater(edge.cost, 0)
            self.assertNotIn(edge.key, edge_keys, f"Duplicate edge key: {edge.key}")
            edge_keys.add(edge.key)
            used_formats.add(edge.source)
            used_formats.add(edge.target)
            preview = edge.command_preview(f"in.{edge.source}", f"out.{edge.target}", opts)
            self.assertIsInstance(preview, list)
            self.assertGreater(len(preview), 0)

        self.assertEqual(used_formats, SUPPORTED_FORMATS)

    def test_direct_pdf_to_svg(self):
        route = self.router.find_route("pdf", "svg", require_available=False)
        self.assertIsNotNone(route)
        self.assertEqual(route.steps, 1)
        self.assertEqual(route.edges[0].engine_name, "pdftocairo")
        self.assertEqual(route.total_cost, 7)

    def test_direct_svg_to_pdf(self):
        route = self.router.find_route("svg", "pdf", require_available=False)
        self.assertIsNotNone(route)
        self.assertEqual(route.steps, 1)
        self.assertEqual(route.edges[0].engine_name, "rsvg-convert")
        self.assertEqual(route.total_cost, 6)

    def test_direct_pdf_to_png(self):
        route = self.router.find_route("pdf", "png", require_available=False)
        self.assertIsNotNone(route)
        self.assertEqual(route.steps, 1)
        self.assertEqual(route.edges[0].engine_name, "pdftoppm")
        self.assertEqual(route.total_cost, 11)

    def test_md_to_docx_primary_and_fallback(self):
        primary = self.router.find_route("md", "docx", require_available=False)
        self.assertIsNotNone(primary)
        self.assertEqual(primary.formats, ["md", "docx"])
        self.assertEqual(primary.edges[0].engine_name, "pandoc")
        self.assertEqual(primary.total_cost, 8)

        with patch("fconv.converters.pandoc.has_pandoc", return_value=False), patch(
            "fconv.converters.macos_native.has_textutil", return_value=True
        ):
            fallback = Router(get_default_edges()).find_route("md", "docx", require_available=True)
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback.formats, ["md", "html", "docx"])
        self.assertEqual([e.engine_name for e in fallback.edges], ["builtin_md", "textutil"])
        self.assertEqual(fallback.total_cost, 15)

    def test_md_to_pdf_primary_and_fallbacks(self):
        primary = self.router.find_route("md", "pdf", require_available=False)
        self.assertIsNotNone(primary)
        self.assertEqual(primary.formats, ["md", "html", "pdf"])
        self.assertEqual([e.engine_name for e in primary.edges], ["pandoc", "chrome"])
        self.assertEqual(primary.total_cost, 19)

        with patch("fconv.converters.browser.has_browser", return_value=False), patch(
            "fconv.converters.pandoc.has_pandoc", return_value=True
        ), patch("fconv.converters.pandoc.has_pandoc_pdf", return_value=True):
            latex_fallback = Router(get_default_edges()).find_route("md", "pdf", require_available=True)
        self.assertIsNotNone(latex_fallback)
        self.assertEqual(latex_fallback.formats, ["md", "pdf"])
        self.assertEqual(latex_fallback.edges[0].engine_name, "pandoc-latex")
        self.assertEqual(latex_fallback.total_cost, 22)

        with patch("fconv.converters.browser.has_browser", return_value=True), patch(
            "fconv.converters.pandoc.has_pandoc", return_value=False
        ), patch("fconv.converters.pandoc.has_pandoc_pdf", return_value=False):
            builtin_fallback = Router(get_default_edges()).find_route("md", "pdf", require_available=True)
        self.assertIsNotNone(builtin_fallback)
        self.assertEqual(builtin_fallback.formats, ["md", "html", "pdf"])
        self.assertEqual([e.engine_name for e in builtin_fallback.edges], ["builtin_md", "chrome"])
        self.assertEqual(builtin_fallback.total_cost, 23)

    def test_docx_and_html_to_md(self):
        for src in ("docx", "html", "rtf"):
            route = self.router.find_route(src, "md", require_available=False)
            self.assertIsNotNone(route)
            self.assertEqual(route.formats, [src, "md"])
            self.assertEqual(route.edges[0].engine_name, "pandoc")

    def test_ocr_and_terminal_only_pdf_wrapper_isolation(self):
        # Raster -> txt must pick tesseract, never sips -> pdftotext
        for src in ("png", "jpg", "tiff"):
            route = self.router.find_route(src, "txt", require_available=False)
            self.assertIsNotNone(route)
            self.assertEqual(route.formats, [src, "txt"])
            self.assertEqual(route.edges[0].engine_name, "tesseract")

        # Raster -> svg must not exist via bitmap PDF wrapper
        self.assertIsNone(self.router.find_route("png", "svg", require_available=False))
        self.assertIsNone(self.router.find_route("jpg", "svg", require_available=False))

        # Direct png -> pdf still works
        pdf_route = self.router.find_route("png", "pdf", require_available=False)
        self.assertIsNotNone(pdf_route)
        self.assertEqual(pdf_route.formats, ["png", "pdf"])

        # pdf -> txt without pdftotext uses pdf -> png -> txt (never direct tesseract)
        with patch("fconv.converters.poppler.has_pdftotext", return_value=False), patch(
            "fconv.converters.poppler.has_pdftoppm", return_value=True
        ), patch("fconv.converters.ocr.has_tesseract", return_value=True):
            ocr_pdf = Router(get_default_edges()).find_route("pdf", "txt", require_available=True)
        self.assertIsNotNone(ocr_pdf)
        self.assertEqual(ocr_pdf.formats, ["pdf", "png", "txt"])
        self.assertEqual([e.engine_name for e in ocr_pdf.edges], ["pdftoppm", "tesseract"])

    def test_webp_to_jpg_never_picks_dwebp_directly(self):
        # On macOS (dwebp + sips)
        with patch("fconv.converters.webp.has_dwebp", return_value=True), patch(
            "fconv.converters.macos_native.has_sips", return_value=True
        ), patch("fconv.converters.imagemagick.has_magick", return_value=True):
            macos_route = Router(get_default_edges()).find_route("webp", "jpg", require_available=True)
        self.assertIsNotNone(macos_route)
        self.assertEqual(macos_route.formats, ["webp", "png", "jpg"])
        self.assertEqual([e.engine_name for e in macos_route.edges], ["dwebp", "sips"])

        # On Linux (magick)
        with patch("fconv.converters.webp.has_dwebp", return_value=True), patch(
            "fconv.converters.macos_native.has_sips", return_value=False
        ), patch("fconv.converters.imagemagick.has_magick", return_value=True):
            linux_route = Router(get_default_edges()).find_route("webp", "jpg", require_available=True)
        self.assertIsNotNone(linux_route)
        self.assertEqual(linux_route.formats, ["webp", "jpg"])
        self.assertEqual(linux_route.edges[0].engine_name, "magick")

    def test_linux_raster_never_detours_through_lossy_webp(self):
        with patch("fconv.converters.macos_native.has_sips", return_value=False), patch(
            "fconv.converters.imagemagick.has_magick", return_value=True
        ), patch("fconv.converters.webp.has_cwebp", return_value=True), patch(
            "fconv.converters.webp.has_dwebp", return_value=True
        ):
            linux_router = Router(get_default_edges())
            jpg_to_png = linux_router.find_route("jpg", "png", require_available=True)
            png_to_jpg = linux_router.find_route("png", "jpg", require_available=True)
            jpg_to_tiff = linux_router.find_route("jpg", "tiff", require_available=True)
        self.assertEqual([e.engine_name for e in jpg_to_png.edges], ["magick"])
        self.assertEqual([e.engine_name for e in png_to_jpg.edges], ["magick"])
        self.assertNotIn("cwebp", [e.engine_name for e in jpg_to_tiff.edges])

    def test_rich_docs_do_not_detour_through_txt(self):
        for src, dst in [("docx", "rtf"), ("rtf", "docx"), ("rtf", "html"), ("txt", "html")]:
            route = self.router.find_route(src, dst, require_available=False)
            self.assertIsNotNone(route)
            self.assertEqual(route.formats, [src, dst])
            self.assertEqual(route.edges[0].engine_name, "textutil")

    def test_router_features_forced_engine_excluded_ties_same_format(self):
        # Case-insensitive forced engine
        route = self.router.find_route("pdf", "svg", forced_engine="Inkscape", require_available=False)
        self.assertIsNotNone(route)
        self.assertEqual(route.edges[0].engine_name, "inkscape")
        self.assertEqual(route.total_cost, 24)

        # Excluded edges skips primary and selects fallback
        no_cairo = self.router.find_route(
            "pdf", "svg", require_available=False, excluded_edges={"pdf->svg:pdftocairo"}
        )
        self.assertEqual(no_cairo.edges[0].engine_name, "inkscape")

        # Same format returns 0-step route
        same = self.router.find_route("png", "png", require_available=True)
        self.assertEqual(same.steps, 0)
        self.assertEqual(same.total_cost, 0)

        # Deterministic tie breaking prefers fewer hops and non-fallback
        e1 = Edge("a", "b", "x1", 5, False, "step1", lambda: True, lambda s, d, o: None, lambda s, d, o: [])
        e2 = Edge("b", "c", "x2", 5, False, "step2", lambda: True, lambda s, d, o: None, lambda s, d, o: [])
        e_direct_fb = Edge("a", "c", "fb", 10, True, "direct fb", lambda: True, lambda s, d, o: None, lambda s, d, o: [])
        e_direct_prim = Edge("a", "c", "prim", 10, False, "direct prim", lambda: True, lambda s, d, o: None, lambda s, d, o: [])
        tie_router = Router([e1, e2, e_direct_fb, e_direct_prim])
        best = tie_router.find_route("a", "c")
        self.assertEqual([e.engine_name for e in best.edges], ["prim"])


if __name__ == "__main__":
    unittest.main()
