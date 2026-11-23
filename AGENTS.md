# AGENTS.md

Guidance for coding agents working in `/Users/meilan/code/convert` (`fconv` / `convert`).

## Project Overview

`fconv` (CLI entrypoints `convert` and `fconv`) is a pure-Python (`>=3.10`) command-line file conversion orchestrator with zero third-party Python dependencies (`pyproject.toml` has `dependencies = []`).

Instead of a hardcoded `(source, target)` matrix, it models formats as vertices (`svg`, `pdf`, `png`, `jpg`, `webp`, `tiff`, `bmp`, `gif`, `md`, `html`, `txt`, `rtf`, `docx`) and external tool adapters as weighted directed edges in a multigraph (`fconv/graph/registry.py`). At runtime, `Router.find_route` (`fconv/graph/router.py`) uses Dijkstra's algorithm over currently available tools to select the lowest-cost single-hop or multi-hop conversion pipeline, and `execute_with_fallback` (`fconv/engine/pipeline.py`) stages intermediate and final outputs inside a temporary directory and retries alternative routes if an unforced engine fails.

## Repository Layout

- `bin/convert`, `bin/fconv`: Executable Python shims that resolve symlinks, prepend the repo root to `sys.path`, and invoke `fconv.cli:main`. (`fconv` is the alias used to avoid `$PATH` collisions with ImageMagick's `convert`.)
- `pyproject.toml`: Package metadata (`setuptools`), console script entrypoints (`convert`, `fconv`), zero runtime dependencies.
- `fconv/cli.py`: `argparse` CLI (`allow_abbrev=False`, numeric validators for `--dpi`/`--quality`/`--page`/`--timeout`, `--engine`, `--from`, `--to`, `--explain`, `--silent`/`--quiet`/`-s`, `--json`, `--verbose`/`-v`, `-V`/`--version`) and diagnostic commands (`doctor`, `install-deps`, `list-tools`).
- `fconv/options.py`: `ConvertOptions` dataclass and `for_intermediate(preserve_dpi_none=...)` helper (keeps intermediate quality >= 95 and avoids forcing 300 DPI onto lossless vector hops).
- `fconv/graph/`:
  - `node.py`: `EXTENSION_MAP`, `SUPPORTED_FORMATS`, `normalize_format()`, `detect_format_from_path()`.
  - `edge.py`: `FidelityClass` enum and `Edge` dataclass (`terminal_only`, `supports_dpi`, `default_dpi`, `get_notice()`).
  - `router.py`: `Route` and `Router` (Dijkstra with deterministic tie-breaking by hop count and fallback count, `terminal_only` guard, `excluded_edges`, availability caching, case-insensitive first-hop `forced_engine`).
  - `registry.py`: `get_default_edges()` — curated atomic conversion edges with explicit costs, fidelity classes, availability checks, execution callbacks, and command previews.
- `fconv/converters/`: External binary adapters and built-in converters:
  - `base.py`: `is_tool_installed()`, `ensure_parent_dir()`.
  - `poppler.py`: `pdftocairo` (`pdf -> svg`), `pdftoppm` (`pdf -> png/jpg/tiff`), `pdftotext` (`pdf -> txt`).
  - `librsvg.py`: `rsvg-convert` (`svg -> pdf/png`).
  - `inkscape.py`: `inkscape` fallback (`pdf -> svg`, `svg -> pdf/png`).
  - `macos_native.py`: `sips` (macOS-only raster and raster-to-PDF wrapping) and `textutil` (macOS-only `html`/`txt`/`rtf`/`docx`).
  - `webp.py`: `cwebp` (`png`/`jpg`/`tiff -> webp`) and `dwebp` (`webp -> png`/`bmp`/`tiff`).
  - `imagemagick.py`: `magick` cross-platform fallback for raster, SVG->PNG, PDF->raster, and raster->PDF.
  - `browser.py`: Headless Google Chrome / Chromium / Brave (`html -> pdf`) using `Path.as_uri()` and `--virtual-time-budget=3000`.
  - `ocr.py`: `tesseract` (`png`/`jpg`/`tiff -> txt`; scanned PDFs route automatically via `pdf -> png -> txt`).
  - `markdown.py`: Zero-dependency Markdown-to-HTML5 fallback parser (`md -> html` via `builtin_md`) with print CSS, `<base href>`, currency/snake_case-safe math protection, and KaTeX snippet injection.
  - `pandoc.py`: `pandoc` (`md -> html` offline MathML + print CSS, `md <-> docx/rtf`, `html/rtf -> md`, document fallbacks) and `pandoc-latex` (`md/html/docx/rtf -> pdf` via `xelatex`/`pdflatex`/`lualatex`/`tectonic`).
- `fconv/engine/`:
  - `process.py`: Augmented `PATH` lookup (`/opt/homebrew/bin`, `/usr/local/bin`, `/Library/TeX/texbin`), `resolve_binary()`, UTF-8 replacement decoding, `stdin=DEVNULL`, POSIX process-group timeout cleanup, `ProcessExecutionError`.
  - `pipeline.py`: `Pipeline` (`explain()` with `shlex.join`, staged `execute()`), `PipelineExecutionError(failed_edge=...)`, and `execute_with_fallback()`.
  - `telemetry.py`: `TelemetryRecord` console summary and `--json` output, `format_bytes()`, `format_ratio()`.
  - `doctor.py`: `TOOLS_SPEC`, `check_all_tools()`, `run_doctor()`, `run_install_deps()`.
- `tests/`: `unittest` suite (`test_graph.py`, `test_converters.py`, `test_telemetry.py`, `test_engine.py`, `test_e2e.py`).

## Common Commands

Run the full test suite:
```bash
python3 -m unittest discover -s tests -v
```

Run only unit tests (no external binaries required):
```bash
python3 -m unittest tests.test_graph tests.test_converters tests.test_telemetry tests.test_engine -v
```

Inspect CLI diagnostics and routing without modifying files:
```bash
python3 bin/convert doctor
python3 bin/convert list-tools
python3 bin/convert --explain input.md output.pdf
```

## Coding & Architecture Conventions

1. **Zero Python package dependencies**: Do not add third-party PyPI packages to `pyproject.toml` or import non-stdlib modules in `fconv/`.
2. **Every converter adapter follows the same pattern**:
   - Provide `has_<tool>() -> bool` using `is_tool_installed(...)` (or custom discovery like `find_browser_binary()` / `find_pdf_engine()`).
   - Provide `build_<src>_to_<dst>_cmd(...) -> List[str]` so `Pipeline.explain()` can preview exact commands without running them.
   - Provide `convert_<src>_to_<dst>(...) -> None` that calls `ensure_parent_dir(dst)` and `run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)`.
3. **Edge registration**:
   - All edges live in `fconv/graph/registry.py` (`get_default_edges()`).
   - Keep `SEMANTIC_DEGRADATION` `-> txt` edge costs at `16+` so rich document conversions never detour through plain text, and mark raster-to-PDF container edges `terminal_only=True`.
   - Assign `FidelityClass` and `supports_dpi` accurately so pre-flight `[NOTICE]` warnings stay truthful.
4. **Doctor sync**: Keep `fconv/engine/doctor.py` (`TOOLS_SPEC` and `run_install_deps()`), `README.md`, and `tests/test_engine.py` in sync with every external engine in `registry.py`.
