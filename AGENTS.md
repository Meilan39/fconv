# AGENTS.md

Guidance for coding agents working in `/Users/meilan/code/convert` (`fconv` / `convert`).

## Project Overview

`fconv` (CLI entrypoints `convert` and `fconv`) is a pure-Python (`>=3.10`) command-line file conversion orchestrator with zero third-party Python dependencies (`pyproject.toml` has `dependencies = []`).

Instead of a hardcoded `(source, target)` matrix, it models formats as vertices and external tool adapters as weighted directed edges in a multigraph (`fconv/graph/registry.py`). At runtime, `Router.find_route` (`fconv/graph/router.py`) uses Dijkstra's algorithm over currently available tools to select the lowest-cost single-hop or multi-hop conversion pipeline, executing intermediate steps inside a temporary directory (`fconv/engine/pipeline.py`).

## Repository Layout

- `bin/convert`, `bin/fconv`: Executable Python shims that resolve symlinks, prepend the repo root to `sys.path`, and invoke `fconv.cli:main`. (`fconv` is the alias used to avoid `$PATH` collisions with ImageMagick's `convert`.)
- `pyproject.toml`: Package metadata (`setuptools`), console script entrypoints (`convert`, `fconv`), zero runtime dependencies.
- `fconv/cli.py`: `argparse` CLI (`--dpi`/`-dpi`/`-d`, `--quality`/`-quality`, `--page`/`-p`/`-page`, `--engine`/`-e`, `--from`, `--to`, `--explain`, `--silent`/`--quiet`/`-s`, `--json`, `--verbose`/`-v`, `--timeout`) and diagnostic commands (`doctor`, `install-deps`, `list-tools`).
- `fconv/options.py`: `ConvertOptions` dataclass and `for_intermediate()` helper (defaults intermediate steps to `dpi=300`, `quality=95`, `engine=None`).
- `fconv/graph/`:
  - `node.py`: `EXTENSION_MAP`, `SUPPORTED_FORMATS`, `normalize_format()`, `detect_format_from_path()`.
  - `edge.py`: `FidelityClass` enum (`LOSSLESS_VECTOR`, `LOSSLESS_RASTER`, `LOSSLESS_CONTAINER`, `VECTOR_RASTERIZATION`, `LOSSY_COMPRESSION`, `SEMANTIC_DEGRADATION`, `PROBABILISTIC_OCR`) and `Edge` dataclass with `get_notice()`.
  - `router.py`: `Route` and `Router` (Dijkstra shortest-path finder with cycle prevention, availability filtering, and first-hop `forced_engine` filtering).
  - `registry.py`: `get_default_edges()` — curated atomic conversion edges with explicit integer costs, fidelity classes, availability checks, execution callbacks, and command previews.
- `fconv/converters/`: External binary adapters and built-in converters:
  - `base.py`: `is_tool_installed()`, `ensure_parent_dir()`.
  - `poppler.py`: `pdftocairo` (`pdf -> svg`), `pdftoppm` (`pdf -> png/jpg`), `pdftotext` (`pdf -> txt`).
  - `librsvg.py`: `rsvg-convert` (`svg -> pdf`, `svg -> png`).
  - `inkscape.py`: `inkscape` fallback (`pdf -> svg`, `svg -> pdf`, `svg -> png`).
  - `macos_native.py`: `sips` (raster conversions and raster-to-PDF wrapping) and `textutil` (`html`/`txt`/`rtf`/`docx`).
  - `webp.py`: `cwebp` and `dwebp` (`png`/`jpg <-> webp`).
  - `imagemagick.py`: `magick` fallback for raster/WebP conversions.
  - `browser.py`: Headless Google Chrome / Chromium / Brave (`html -> pdf`).
  - `ocr.py`: `tesseract` (`png`/`jpg`/`pdf -> txt`).
  - `markdown.py`: Zero-dependency Markdown-to-HTML5 parser (`md -> html`).
- `fconv/engine/`:
  - `process.py`: `resolve_binary()`, `run_process()`, `ProcessExecutionError`.
  - `pipeline.py`: `Pipeline` (`explain()` dry-run printer, single-hop/multi-hop `execute()`, `PipelineExecutionError`).
  - `telemetry.py`: `TelemetryRecord` console summary and `--json` output, `format_bytes()`, `format_ratio()`.
  - `doctor.py`: `TOOLS_SPEC`, `check_all_tools()`, `run_doctor()`, `run_install_deps()`.
- `tests/`: `unittest` suite (`test_graph.py`, `test_converters.py`, `test_telemetry.py`, `test_e2e.py`).
- `implementation_plan.md`: Initial design specification (some details differ from the final implementation, e.g. `cwebp`/`dwebp` are primary for WebP rather than `magick`).

## Common Commands

Run the full test suite:
```bash
python3 -m unittest discover -s tests -v
```

Run only pure unit tests (no external binaries required):
```bash
python3 -m unittest tests.test_graph tests.test_converters tests.test_telemetry -v
```

Inspect CLI diagnostics and routing without modifying files:
```bash
python3 bin/convert doctor
python3 bin/convert list-tools
python3 bin/convert --explain input.md output.png
```

## Coding & Architecture Conventions

1. **Zero Python package dependencies**: Do not add third-party PyPI packages to `pyproject.toml` or import non-stdlib modules in `fconv/`.
2. **Every converter adapter follows the same pattern**:
   - Provide `has_<tool>() -> bool` using `is_tool_installed(...)` (or custom discovery like `find_browser_binary()`).
   - Provide `build_<src>_to_<dst>_cmd(src, dst, opts) -> List[str]` so `Pipeline.explain()` can preview exact commands without running them.
   - Provide `convert_<src>_to_<dst>(src, dst, opts) -> None` that calls `ensure_parent_dir(dst)` and `run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)`.
3. **Edge registration**:
   - All edges live in `fconv/graph/registry.py` (`get_default_edges()`).
   - Assign `cost` intentionally (lower cost wins in Dijkstra): fast native/C tools (`4`–`12`), heavy runtimes (`14`–`25`), OCR (`38`–`45`).
   - Always assign an accurate `FidelityClass` so pre-flight `[NOTICE]` warnings and telemetry stay truthful.
4. **Doctor sync**: When adding or removing an external engine in `registry.py`, check `fconv/engine/doctor.py` (`TOOLS_SPEC` and `run_install_deps()`), `README.md`, and `tests/test_graph.py` / `tests/test_converters.py`.

## Known Quirks & Caveats

- **`tests/test_e2e.py` is environment-dependent**: It runs real conversions (`svg -> pdf`, `svg -> png`, `pdf -> svg`, `pdf -> png`, `md -> html`, `md -> docx`, `png -> jpg`, `png <-> webp`). Missing tools on `$PATH` (or macOS sandbox restrictions blocking `textutil` HTML-to-DOCX Cocoa conversion) will cause failures in `test_e2e.py`.
- **`doctor.py` vs `registry.py` drift**: `TOOLS_SPEC` in `fconv/engine/doctor.py` does not currently include `rsvg-convert`, `magick`, or `tesseract`, even though `registry.py` registers edges for them and `run_install_deps()` recommends installing them.
- **`--engine` scope**: `Router.find_route(..., forced_engine=...)` only constrains the first hop (`len(path) == 0`) of a route.
- **Unused normalized extensions**: `node.py` maps `bmp` and `gif` (and `macos_native._format_for_sips` recognizes them), and `svgz` maps to `svg`, though `registry.py` has no `bmp`/`gif` edges.
- **macOS-only tools**: `sips` and `textutil` are macOS native binaries; on non-macOS systems their `check_available` checks return `False` and the router skips those edges.
