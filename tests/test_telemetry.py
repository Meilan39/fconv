"""Unit tests for telemetry formatting, compression ratio, and fidelity notices."""

import json
import unittest
from fconv.engine.telemetry import TelemetryRecord, format_bytes, format_ratio
from fconv.graph.edge import Edge, FidelityClass
from fconv.options import ConvertOptions


class TestTelemetry(unittest.TestCase):
    def test_format_bytes(self):
        self.assertEqual(format_bytes(512), "512 B")
        self.assertEqual(format_bytes(1024), "1.0 KB")
        self.assertEqual(format_bytes(1536), "1.5 KB")
        self.assertEqual(format_bytes(1024 * 1024 * 2), "2.0 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024 * 3), "3.00 GB")

    def test_format_ratio(self):
        self.assertEqual(format_ratio(100, 50), "-50.0%")
        self.assertEqual(format_ratio(100, 200), "+100.0%")
        self.assertEqual(format_ratio(100, 100), "+0.0%")
        self.assertEqual(format_ratio(0, 500), "N/A")
        self.assertEqual(format_ratio(0, 0), "+0.0%")
        self.assertEqual(format_ratio(10000, 9999), "+0.0%")

    def test_edge_notices(self):
        raster_edge = Edge(
            source="svg",
            target="png",
            engine_name="rsvg-convert",
            cost=11,
            is_fallback=False,
            fidelity=FidelityClass.VECTOR_RASTERIZATION,
            description="test",
            check_available=lambda: True,
            execute=lambda s, d, o: None,
            command_preview=lambda s, d, o: [],
        )
        opts = ConvertOptions(dpi=300)
        notice = raster_edge.get_notice(opts)
        self.assertIn("Irreversible vector rasterization", notice)
        self.assertIn("300 DPI", notice)

        no_dpi_edge = Edge(
            source="pdf",
            target="png",
            engine_name="sips",
            cost=24,
            is_fallback=True,
            fidelity=FidelityClass.VECTOR_RASTERIZATION,
            description="test",
            check_available=lambda: True,
            execute=lambda s, d, o: None,
            command_preview=lambda s, d, o: [],
            supports_dpi=False,
        )
        self.assertEqual(no_dpi_edge.get_notice(opts), "Irreversible vector rasterization (PDF -> PNG)")

        for fidelity in (
            FidelityClass.LOSSY_COMPRESSION,
            FidelityClass.SEMANTIC_DEGRADATION,
            FidelityClass.PROBABILISTIC_OCR,
        ):
            e = Edge("png", "txt", "eng", 10, False, "desc", lambda: True, lambda s, d, o: None, lambda s, d, o: [], fidelity)
            self.assertIsNotNone(e.get_notice(ConvertOptions(quality=80)))

        lossless_edge = Edge(
            source="svg",
            target="pdf",
            engine_name="rsvg-convert",
            cost=6,
            is_fallback=False,
            fidelity=FidelityClass.LOSSLESS_VECTOR,
            description="test",
            check_available=lambda: True,
            execute=lambda s, d, o: None,
            command_preview=lambda s, d, o: [],
        )
        self.assertIsNone(lossless_edge.get_notice(opts))

    def test_telemetry_record_render_and_zero_bytes_json(self):
        record = TelemetryRecord(
            source_path="/path/to/diagram.svg",
            target_path="/path/to/diagram.png",
            source_bytes=1000,
            target_bytes=2500,
            duration_ms=1250.0,
            engines=["rsvg-convert"],
            fidelities=["vector_rasterization"],
            notices=["Irreversible vector rasterization"],
            options_summary=["300 DPI"],
        )
        summary = record.render_console_summary()
        self.assertIn("[SUCCESS]", summary)
        self.assertIn("diagram.svg", summary)
        self.assertIn("diagram.png", summary)
        self.assertIn("+150.0%", summary)
        self.assertIn("300 DPI", summary)
        self.assertIn("1.25s via rsvg-convert", summary)

        parsed = json.loads(record.to_json())
        self.assertEqual(parsed["source_bytes"], 1000)
        self.assertEqual(parsed["target_bytes"], 2500)
        self.assertEqual(parsed["ratio"], 2.5)

        empty_to_nonempty = TelemetryRecord("a", "b", 0, 100, 1.0, ["copy"], ["lossless_container"], [], [])
        self.assertIsNone(json.loads(empty_to_nonempty.to_json())["ratio"])

        empty_to_empty = TelemetryRecord("a", "b", 0, 0, 1.0, ["copy"], ["lossless_container"], [], [])
        self.assertEqual(json.loads(empty_to_empty.to_json())["ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
