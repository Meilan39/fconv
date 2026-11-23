"""Unit tests for process execution, pipeline staging/fallback, CLI, and doctor."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from fconv.cli import main
from fconv.engine.doctor import TOOLS_SPEC
from fconv.engine.pipeline import Pipeline, PipelineExecutionError, execute_with_fallback
from fconv.engine.process import ProcessExecutionError, run_process
from fconv.graph.edge import Edge, FidelityClass
from fconv.graph.registry import get_default_edges
from fconv.graph.router import Route, Router
from fconv.options import ConvertOptions


class TestEngineAndCLI(unittest.TestCase):
    def test_options_for_intermediate(self):
        opts = ConvertOptions(dpi=None, quality=25, page=2)
        inter = opts.for_intermediate()
        self.assertEqual(inter.dpi, 300)
        self.assertEqual(inter.quality, 95)
        self.assertEqual(inter.page, 2)

        vec_inter = opts.for_intermediate(preserve_dpi_none=True)
        self.assertIsNone(vec_inter.dpi)

    def test_run_process_binary_missing_utf8_and_timeout(self):
        with self.assertRaises(ProcessExecutionError) as ctx:
            run_process(["definitely_missing_fconv_bin_xyz"])
        self.assertEqual(ctx.exception.exit_code, 127)

        # Non-UTF8 output should decode cleanly without UnicodeDecodeError
        res = run_process([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'ok\\xff\\n')"])
        self.assertIn("ok", res.stdout)

        # Verify stdin is isolated (DEVNULL) and TimeoutExpired handles bytes cleanly
        res_stdin = run_process([sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"])
        self.assertEqual(res_stdin.stdout.strip(), "0")

        with self.assertRaises(ProcessExecutionError) as timeout_ctx:
            run_process([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
        self.assertEqual(timeout_ctx.exception.exit_code, 124)
        self.assertIsInstance(timeout_ctx.exception.stdout, str)

    def test_pipeline_single_hop_errors_samefile_and_directory_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.png")
            with open(src, "wb") as f:
                f.write(b"PNGDATA")

            bad_edge = Edge(
                "png", "jpg", "broken", 5, False, "fails",
                lambda: True,
                lambda s, d, o: (_ for _ in ()).throw(RuntimeError("boom")),
                lambda s, d, o: ["broken", s, d],
            )
            with self.assertRaises(PipelineExecutionError) as err_ctx:
                Pipeline(Route("png", "jpg", [bad_edge], 5), ConvertOptions()).execute(src, os.path.join(tmp, "out.jpg"))
            self.assertIs(err_ctx.exception.failed_edge, bad_edge)

            noop_edge = Edge(
                "png", "jpg", "noop", 5, False, "writes nothing",
                lambda: True,
                lambda s, d, o: None,
                lambda s, d, o: ["noop", s, d],
            )
            with self.assertRaises(PipelineExecutionError):
                Pipeline(Route("png", "jpg", [noop_edge], 5), ConvertOptions()).execute(src, os.path.join(tmp, "out.jpg"))

            # Directory source/destination rejected
            with self.assertRaises(PipelineExecutionError):
                Pipeline(Route("png", "png", [], 0), ConvertOptions()).execute(tmp, os.path.join(tmp, "out.png"))
            with self.assertRaises(PipelineExecutionError):
                Pipeline(Route("png", "png", [], 0), ConvertOptions()).execute(src, tmp)

            # Same file copy creates parent dirs and ignores samefile safely
            nested_copy = os.path.join(tmp, "sub", "copy.png")
            rec = Pipeline(Route("png", "png", [], 0), ConvertOptions()).execute(src, nested_copy)
            self.assertTrue(os.path.isfile(nested_copy))
            self.assertEqual(rec.fidelities, ["lossless_container"])

            rec_same = Pipeline(Route("png", "png", [], 0), ConvertOptions()).execute(src, src)
            self.assertEqual(rec_same.source_bytes, len(b"PNGDATA"))

            # Same path with transform stages safely without corrupting input before reading
            def _transform_same(s, d, o):
                with open(s, "rb") as rf, open(d, "wb") as wf:
                    wf.write(rf.read() + b"_MOD")

            mod_edge = Edge("png", "jpg", "mod", 5, False, "mod", lambda: True, _transform_same, lambda s, d, o: [])
            Pipeline(Route("png", "jpg", [mod_edge], 5), ConvertOptions()).execute(src, src)
            with open(src, "rb") as f:
                self.assertEqual(f.read(), b"PNGDATA_MOD")

    def test_execute_with_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.md")
            dst = os.path.join(tmp, "out.pdf")
            with open(src, "w", encoding="utf-8") as f:
                f.write("# Hello")

            primary = Edge(
                "md", "pdf", "prim", 5, False, "fails",
                lambda: True,
                lambda s, d, o: (_ for _ in ()).throw(RuntimeError("latex missing pkg")),
                lambda s, d, o: ["prim"],
            )

            def _fallback_exec(s, d, o):
                with open(d, "wb") as wf:
                    wf.write(b"%PDF-1.4\n")

            fallback = Edge(
                "md", "pdf", "fb", 10, True, "works",
                lambda: True,
                _fallback_exec,
                lambda s, d, o: ["fb"],
            )
            router = Router([primary, fallback])
            stderr_buf = io.StringIO()
            with redirect_stderr(stderr_buf):
                rec = execute_with_fallback(router, "md", "pdf", src, dst, ConvertOptions())
            self.assertIsNotNone(rec)
            self.assertEqual(rec.engines, ["fb"])
            self.assertIn("[FALLBACK]", stderr_buf.getvalue())
            self.assertTrue(os.path.isfile(dst))

    def test_cli_validation_subcommands_explain_and_json_purity(self):
        # allow_abbrev=False rejects -q
        stderr_buf = io.StringIO()
        with redirect_stderr(stderr_buf), self.assertRaises(SystemExit) as sys_exit:
            main(["a.png", "b.jpg", "-q"])
        self.assertEqual(sys_exit.exception.code, 2)

        # Out-of-range numeric flags rejected
        for bad_args in (["a.png", "b.jpg", "--dpi", "0"], ["a.png", "b.jpg", "--quality", "101"], ["a.png", "b.jpg", "--page", "0"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as se:
                main(bad_args)
            self.assertEqual(se.exception.code, 2)

        # Invalid explicit --from error message
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["doctor", "out.pdf", "--from", "nope"])
        self.assertEqual(code, 1)
        self.assertIn("Unsupported source format 'nope'", err.getvalue())

        # --json --verbose keeps stdout valid JSON
        with tempfile.TemporaryDirectory() as tmp:
            md = os.path.join(tmp, "note.md")
            html_out = os.path.join(tmp, "note.html")
            with open(md, "w", encoding="utf-8") as f:
                f.write("# JSON Test\n")
            out_buf = io.StringIO()
            err_buf = io.StringIO()
            with redirect_stdout(out_buf), redirect_stderr(err_buf):
                code = main([md, html_out, "--engine", "builtin_md", "--json", "--verbose"])
            self.assertEqual(code, 0)
            payload = json.loads(out_buf.getvalue())
            self.assertEqual(payload["engines"], ["builtin_md"])
            self.assertIn("[CONVERT]", err_buf.getvalue())

    def test_doctor_tracks_all_registry_engines(self):
        tracked = {spec[0] for spec in TOOLS_SPEC}
        for edge in get_default_edges():
            if edge.engine_name == "builtin_md":
                continue
            if edge.engine_name == "pandoc-latex":
                self.assertIn("pandoc", tracked)
                self.assertIn("tex-engine", tracked)
            else:
                self.assertIn(edge.engine_name, tracked, f"Engine '{edge.engine_name}' missing from doctor TOOLS_SPEC")


if __name__ == "__main__":
    unittest.main()
