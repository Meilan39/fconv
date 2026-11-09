"""Unit tests for format normalization, edge registry, and Dijkstra router."""

import unittest
from fconv.graph.node import detect_format_from_path, normalize_format
from fconv.graph.registry import get_default_edges
from fconv.graph.router import Router


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

    def test_detect_format_from_path(self):
        self.assertEqual(detect_format_from_path("/path/to/diagram.SVG"), "svg")
        self.assertEqual(detect_format_from_path("photo.jpeg"), "jpg")
        self.assertEqual(detect_format_from_path("README.md"), "md")

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

    def test_multi_hop_md_to_docx(self):
        route = self.router.find_route("md", "docx", require_available=False)
        self.assertIsNotNone(route)
        self.assertEqual(route.formats, ["md", "html", "docx"])
        self.assertEqual(route.total_cost, 11)

    def test_multi_hop_md_to_pdf(self):
        route = self.router.find_route("md", "pdf", require_available=False)
        self.assertIsNotNone(route)
        self.assertEqual(route.formats, ["md", "html", "pdf"])
        self.assertEqual(route.total_cost, 21)

    def test_forced_engine(self):
        route = self.router.find_route("pdf", "svg", forced_engine="inkscape", require_available=False)
        self.assertIsNotNone(route)
        self.assertEqual(route.edges[0].engine_name, "inkscape")
        self.assertEqual(route.total_cost, 24)


if __name__ == "__main__":
    unittest.main()
