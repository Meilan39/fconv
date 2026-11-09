# Universal File Converter (`fconv` / `convert`)

A lightweight, high-performance command-line conversion utility. It automatically infers source and target formats from file extensions, navigates an explicitly scored directed multigraph using Dijkstra's shortest-path algorithm, and chains native system utilities and lightweight command-line tools.

---

## Key Features

- **Automatic Format Detection**: Infers input and output formats directly from file paths (for example, `convert diagram.svg figure.pdf`).
- **Directed Graph Routing**: Models formats as vertices and conversion adapters as directed weighted edges. Prioritizes vector preservation, visual fidelity, and native tool execution speed.
- **Transparent Multi-Hop Pipelines**: Discovers and chains intermediate transformations (such as `md -> html -> docx` or `md -> html -> pdf -> png`) in isolated temporary directories with automatic cleanup.
- **Fidelity Warnings & Size Telemetry**: Warns before executing lossy compression or vector rasterization, and reports file size deltas, compression ratios, and execution durations upon completion.
- **Zero Heavy Python Dependencies**: Built on Python 3 standard library modules without requiring external pip wheels.
- **Customizable Parameters**: Supports output resolution (`-dpi=300` or `--dpi 300`), page extraction (`--page 1`), lossy quality tuning (`--quality 85`), engine forcing (`--engine inkscape`), and dry-run diagnostics (`--explain`).

---

## Supported Formats

| Format | Category | Optimal Tools | Fidelity Guarantee |
| :--- | :--- | :--- | :--- |
| **SVG** | Vector Graphics | `pdftocairo`, `rsvg-convert`, `inkscape` | Lossless vector curves |
| **PDF** | Portable Document | `pdftocairo`, `pdftoppm`, `pdftotext`, `rsvg-convert`, `sips` | Native vector or anti-aliased raster |
| **PNG / JPG / TIFF** | Raster Images | macOS `sips`, `pdftoppm` | Hardware-accelerated or lossless |
| **WEBP** | Modern Raster | Google `cwebp`, `dwebp` | High-efficiency compression |
| **MD** | Markdown | Built-in zero-dependency parser | Clean semantic HTML5 |
| **HTML** | Web Document | macOS `textutil`, headless Google Chrome | Full CSS paged media or structured text |
| **TXT / RTF / DOCX** | Text & Documents | macOS `textutil` Cocoa engine | Native document layout |

---

## Installation & Setup

### Method 1: Symlink Executable Shims (Recommended for local dev)

Clone the repository and link the standalone executable shims to a directory in your `$PATH` (such as `~/.local/bin`):

```bash
git clone https://github.com/<your-username>/fconv.git
cd fconv

mkdir -p ~/.local/bin
ln -sf "$(pwd)/bin/convert" ~/.local/bin/convert
ln -sf "$(pwd)/bin/fconv" ~/.local/bin/fconv
```

Ensure `~/.local/bin` is in your shell search path:
```zsh
export PATH="$HOME/.local/bin:$PATH"
```

### Method 2: Install via pip / pipx

Install as an editable package into your active Python environment:
```bash
pip install -e .
```
Or install in an isolated CLI environment via pipx:
```bash
pipx install .
```

Verify your environment and available conversion engines:
```bash
convert doctor
```

---

## Command Line Usage

### 1. Vector Transformations
```bash
# Vector PDF to SVG extraction via Poppler Cairo backend
convert document.pdf page.svg --page 1

# Flawless SVG to vector PDF
convert diagram.svg figure.pdf
```

### 2. High-Resolution Rasterization with DPI
```bash
# Rasterize SVG to PNG at 300 DPI
convert diagram.svg render.png -dpi=300

# Rasterize PDF page to 600 DPI PNG
convert document.pdf page1.png --dpi 600 --page 1

# Convert PNG to JPEG with 85% quality
convert photo.png photo.jpg --quality 85

# Convert PNG to WebP with 80% quality
convert photo.png photo.webp --quality 80
```

### 3. Markdown and Document Conversions
```bash
# Markdown to styled HTML5
convert notes.md notes.html

# Markdown to Microsoft Word DOCX (chains md -> html -> docx via textutil)
convert notes.md document.docx

# Markdown to PDF (chains md -> html -> pdf via headless Chrome)
convert notes.md report.pdf
```

### 4. Text Extraction
```bash
# Instant extraction of PDF text layer to plain text
convert paper.pdf paper.txt

# Extract structured text from HTML or DOCX
convert document.docx notes.txt
```

### 5. Diagnostics, Fidelity Warnings & Telemetry
```bash
# Preview the planned route, fidelity warnings, and commands without converting
convert --explain notes.md preview.png

# Check status of all system engines
convert doctor

# List all registered transformation edges with fidelity classification
convert list-tools

# Output structured telemetry record as JSON
convert diagram.svg render.png -dpi=300 --json

# Run silently for script automation (errors still printed to stderr)
convert diagram.svg render.png --silent
```

---

## Memory and Performance Characteristics

- **Disk Footprint**: Pure Python implementation with zero third-party pip dependencies. Total repository footprint on disk is under 300 KB.
- **Runtime RAM Usage**:
  - Native tools (`sips`, `textutil`, `pdftotext`, `cwebp`, `dwebp`): 10 to 25 MB RAM.
  - PDF rasterization (`pdftoppm`): 25 to 50 MB RAM depending on DPI resolution.
  - Heavy fallbacks (`inkscape`, headless Chrome): 100 to 250 MB RAM.
- **Ephemeral Process Model**: All external engines execute as discrete child processes that terminate immediately upon completing their transformation step, instantly releasing all allocated memory back to the operating system.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
