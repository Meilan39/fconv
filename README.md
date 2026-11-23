# Universal File Converter (`fconv` / `convert`)

A lightweight, high-performance command-line conversion utility. It automatically infers source and target formats from file extensions, navigates an explicitly scored directed multigraph using Dijkstra's shortest-path algorithm, chains native system utilities and external CLI tools, and automatically retries fallback routes when an unforced engine fails.

---

## Key Features

- **Automatic Format Detection**: Infers input and output formats directly from file paths (for example, `convert diagram.svg figure.pdf`), or accepts explicit `--from` and `--to` overrides.
- **Directed Graph Routing**: Models 13 formats as vertices and conversion adapters as directed weighted edges, prioritizing vector preservation, visual fidelity, and native execution speed.
- **Transparent Multi-Hop Pipelines & Automatic Fallbacks**: Chains intermediate transformations (such as `md -> html -> pdf` or `pdf -> png -> txt`) in isolated temporary directories with automatic cleanup, and automatically retries alternative edges if an unforced engine fails at runtime.
- **Fidelity Warnings & Size Telemetry**: Prints pre-flight `[NOTICE]` warnings to `stderr` before executing lossy compression, vector rasterization, semantic flattening, or OCR, and reports file size deltas, ratios, and timings cleanly (including `--json` machine output).
- **Zero Heavy Python Dependencies**: Built purely on Python 3 standard library modules (`>=3.10`) without third-party PyPI packages.
- **Customizable Parameters**: Supports resolution (`-dpi=300` / `--dpi 300`), lossy quality (`--quality 85`), page selection (`--page 1`), first-hop engine forcing (`--engine inkscape`), timeout control (`--timeout 60`), and route dry-run (`--explain`).

---

## Supported Formats

| Format | Category | Tools (Primary & Fallbacks) | Platform / Fidelity Notes |
| :--- | :--- | :--- | :--- |
| **SVG** | Vector Graphics | `pdftocairo`, `rsvg-convert`, `inkscape`, `magick` | Lossless vector curves (`PDF <-> SVG`, `SVG -> PNG`) |
| **PDF** | Portable Document | `pdftocairo`, `pdftoppm`, `pdftotext`, `rsvg-convert`, `inkscape`, `chrome`, `pandoc`, `magick`, `sips` (macOS) | Native vector, headless CSS/MathML print, or anti-aliased raster |
| **PNG / JPG** | Raster Images | `sips` (macOS), `magick`, `pdftoppm` | Hardware-accelerated macOS native or cross-platform ImageMagick |
| **TIFF / BMP / GIF** | Raster Images | `sips` (macOS), `magick`, `dwebp`, `pdftoppm` (`pdf -> tiff`) | `PNG -> GIF` quantizes colors; `GIF -> PNG` extracts frame 1 |
| **WEBP** | Modern Raster | `cwebp`, `dwebp`, `sips` (macOS `webp -> png`), `magick` | Direct `dwebp` to PNG/TIFF/BMP; `dwebp -> sips` or `magick` to JPG |
| **MD** | Markdown | `pandoc` (MathML + GFM + OMML), built-in zero-dep parser | Bidirectional (`MD <-> HTML/DOCX/RTF`, `MD -> PDF/TXT`) |
| **HTML** | Web Document | Headless Chrome/Chromium/Brave, `pandoc`, `textutil` (macOS) | Full CSS `@page` + offline MathML PDF or document interchange |
| **TXT / RTF / DOCX** | Text & Documents | `pandoc`, `textutil` (macOS), `tesseract` (OCR from PNG/JPG/TIFF) | Rich document interchange plus OCR transcription for scanned images |

> **Note**: `sips` and `textutil` are macOS-only native engines. On Linux, `magick` and `pandoc` provide full cross-platform coverage.

---

## Installation & Setup

### Method 1: Symlink Executable Shims (Recommended for local dev)

Clone the repository and link the standalone executable shims to a directory in your `$PATH` (such as `~/.local/bin`):

```bash
cd /path/to/convert
mkdir -p ~/.local/bin
ln -sf "$(pwd)/bin/convert" ~/.local/bin/convert
ln -sf "$(pwd)/bin/fconv" ~/.local/bin/fconv
```

Ensure `~/.local/bin` is in your shell search path:
```zsh
export PATH="$HOME/.local/bin:$PATH"
```

### Method 2: Install via pip / pipx

```bash
pip install -e .
# or isolated CLI install:
pipx install .
```

Verify your environment and external conversion engines:
```bash
convert doctor
convert install-deps
```

---

## Command Line Usage

### 1. Markdown & Math to PDF / DOCX
- **Default `md -> pdf` pipeline**: Uses `pandoc` to compile GitHub/academic Markdown with native offline **MathML** and print CSS into standalone HTML5, then renders via **headless Chrome** (`pandoc -> chrome`, cost 19). This avoids narrow page margins, handles inline `$...$`, `$$...$$`, `\(...\)`, `\[...\]`, `aligned`/`cases`, tables, task lists, Unicode, and emoji without requiring online CDNs or obscure LaTeX packages.
- **Alternative `md -> pdf` engines**:
  - `--engine pandoc-latex`: Typesets directly through `pandoc` + `xelatex`/`pdflatex`/`lualatex`/`tectonic` (cost 22).
  - `--engine builtin_md`: Uses the zero-dependency built-in Markdown parser + Chrome (cost 23), useful if `pandoc` is not installed.

```bash
# Recommended math-aware Markdown to PDF (pandoc MathML + headless Chrome)
convert notes.md notes.pdf

# Force pure LaTeX typesetting via Pandoc + XeLaTeX/TeX
convert notes.md notes.pdf --engine pandoc-latex

# Force zero-dependency built-in Markdown parser -> Chrome PDF
convert notes.md notes.pdf --engine builtin_md

# Markdown to DOCX (direct Pandoc with native Word equations when installed, else md -> html -> docx)
convert notes.md document.docx

# Extract Markdown back from DOCX or HTML
convert document.docx extracted.md
```

### 2. Vector & High-Resolution Rasterization
```bash
# Vector PDF to SVG extraction via Poppler Cairo backend
convert document.pdf page.svg --page 1

# SVG to vector PDF
convert diagram.svg figure.pdf

# Rasterize SVG to PNG at 300 DPI
convert diagram.svg render.png -dpi=300

# Rasterize PDF page 2 to 600 DPI PNG
convert document.pdf page2.png --dpi 600 --page 2

# Convert PNG to JPEG with 85% quality or WebP with 80% quality
convert photo.png photo.jpg --quality 85
convert photo.png photo.webp --quality 80
```

### 3. Text Extraction & OCR
```bash
# Instant extraction of PDF embedded text layer
convert paper.pdf paper.txt

# OCR transcription from raster image (or scanned PDF via automatic pdf -> png -> txt)
convert scan.png scan.txt
convert scanned_doc.pdf ocr.txt --engine pdftoppm
```

### 4. Explicit Format Overrides, Diagnostics & Telemetry
```bash
# Override inferred formats and execution timeout
convert blob.dat output.bin --from png --to jpg --timeout 120

# Preview route, fidelity warnings, and exact shell commands without executing
convert --explain notes.md preview.png

# System diagnostics and tool listing
convert doctor          # or: convert --doctor
convert install-deps    # or: convert --install-deps
convert list-tools      # or: convert --list-tools
convert --version

# Structured JSON telemetry to stdout with verbose logs routed cleanly to stderr
convert diagram.svg render.png -dpi=300 --json --verbose

# Run silently (errors still printed to stderr)
convert diagram.svg render.png --silent
```

---

## Memory and Performance Characteristics

- **Disk Footprint**: Pure Python implementation with zero third-party pip dependencies. Total repository footprint on disk is under 300 KB.
- **Runtime RAM Usage**:
  - Native tools (`sips`, `textutil`, `pdftotext`, `cwebp`, `dwebp`): ~10–25 MB RAM.
  - PDF rasterization (`pdftoppm`, `rsvg-convert`): ~25–60 MB RAM depending on DPI.
  - Heavy runtimes (`inkscape`, headless Chrome, `pandoc` / `xelatex`): ~100–250 MB RAM.
- **Ephemeral Process Model**: All external engines execute as isolated child processes (`stdin=DEVNULL`, POSIX process-group timeout cleanup) and exit immediately after completing their step.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
