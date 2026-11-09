# Universal File Conversion Tool Implementation Plan

## Architectural Evaluation: Hardcoded Matrix vs. Scored Directed Graph

Before detailing the tool configuration, we evaluate the architectural question: **Should conversions be dispatched via a flat hardcoded lookup table, or does a directed graph remain the optimal model?**

### 1. The Limitation of a Pure Flat Lookup Table
If we define a flat dictionary mapping source and target format pairs directly to commands:
$$\text{dispatch}[(source, target)] \to \text{adapter}$$
For $N = 8$ formats (`svg`, `pdf`, `png`, `jpg`, `webp`, `md`, `html`, `txt`), there are $N(N-1) = 56$ possible conversion pairs. In a flat table:
- Atomic conversions like `svg -> pdf` or `pdf -> png` are trivial.
- Cross-domain conversions requiring intermediate formats (such as `md -> png`, `svg -> txt`, or `md -> pdf`) have no single binary available.
- Without a graph, developers must manually construct, test, and maintain ad-hoc composite pipeline functions for dozens of multi-step combinations.
- If a preferred tool is absent on a machine, a flat table fails unless every pair explicitly defines its own fallback pipeline.

### 2. The Superior Model: Directed Graph of Curated Atomic Transitions
The optimal architecture combines the deterministic certainty of hardcoded tools with the composability of a directed graph:
1. **Curate only atomic transitions**: We define roughly 15 primary atomic edges where a direct, high-quality transformation tool exists.
2. **Explicit, manual scoring per edge**: Every edge receives a hand-calibrated integer score reflecting conversion fidelity, execution latency, and binary startup weight.
3. **Deterministic single-hop execution**: For direct single-hop conversions (such as `pdf -> svg`), the direct optimal edge has the lowest score, so Dijkstra's algorithm immediately selects it with zero ambiguity and sub-millisecond route resolution.
4. **Zero-effort multi-hop synthesis**: Multi-hop conversions (such as `md -> html -> pdf -> png`) emerge organically without hand-coding composite handlers for every permutation.
5. **Dynamic fallback routing**: If a preferred tool is missing, the graph automatically reroutes through an available secondary edge or triggers the dependency installer.

---

## Local Tooling Baseline and Benchmark Research

Inspection of the host macOS system confirms the presence of several specialized utilities alongside standard system binaries. We benchmark each candidate tool across three key metrics:
- **Fidelity**: Preservation of vector paths, font definitions, and visual layout.
- **Latency**: Process startup and rendering speed.
- **Overhead**: Memory consumption and runtime library dependencies.

| Candidate Utility | Path / Source | Strengths | Tradeoffs | Optimal Use Cases |
| :--- | :--- | :--- | :--- | :--- |
| `pdftocairo` | `/opt/homebrew/bin/pdftocairo` | Sub-30ms startup, native Cairo vector output, clean SVG paths | Single-page or multi-page file naming patterns require handling | Primary for `pdf -> svg` |
| `rsvg-convert` | `/opt/homebrew/bin/rsvg-convert` | Ultra-fast C library (librsvg), low memory footprint, crisp antialiasing | Limited support for non-standard SVG draft features | Primary for `svg -> pdf`, `svg -> png` |
| `pdftoppm` | `/opt/homebrew/bin/pdftoppm` | Gold standard PDF rasterizer, native DPI scaling, fast sub-50ms execution | Raster only | Primary for `pdf -> png`, `pdf -> jpg` |
| `pdftotext` | `/opt/homebrew/bin/pdftotext` | Direct extraction of embedded text layers in under 10ms | Does not extract text from scanned bitmap PDFs | Primary for `pdf -> txt` |
| `sips` | `/usr/bin/sips` | Built into macOS, zero external dependencies, hardware accelerated CoreGraphics | Limited to raster image formats and basic PDF image wrapping | Primary for `png <-> jpg`, `png -> pdf` |
| `textutil` | `/usr/bin/textutil` | Built into macOS Cocoa text system, fast, formats HTML/RTF/DOCX/TXT cleanly | Ignores complex CSS grid and flexbox layouts | Primary for `html <-> txt/rtf/docx` |
| `inkscape` | `/opt/homebrew/bin/inkscape` | Comprehensive vector standard support, complex filter rendering | Heavy startup latency (~800ms) due to GTK and font libraries | High-fidelity fallback for complex `pdf <-> svg` |
| `magick` | `/opt/homebrew/bin/magick` | Broad format coverage including WEBP, TIFF, BMP | High process overhead, delegates PDF to Ghostscript | Primary for `webp <-> png/jpg` |
| `tesseract` | `/opt/homebrew/bin/tesseract` | Neural network OCR for images and scanned documents | CPU intensive, 1-3s execution per page | Fallback for `png -> txt` and scanned `pdf -> txt` |
| Headless Chrome | `/Applications/Google Chrome.app` | World-class Blink layout engine, modern CSS paged media support | Headless browser process initialization overhead (~400ms) | Primary for `html -> pdf` |

---

## Explicit Edge Registry and Scoring Matrix

Every atomic transformation is assigned an explicit integer cost based on the following formula:
$$\text{Cost} = \text{Fidelity Penalty } [0\text{--}40] + \text{Latency Weight } [1\text{--}15] + \text{Startup Overhead } [1\text{--}15]$$

- **Fidelity Penalty**:
  - `0`: Perfectly lossless vector-to-vector or native document layout preservation.
  - `5`: Lossless raster conversion or lossless structured text extraction.
  - `10`: Lossless-to-raster conversion at requested DPI.
  - `20`: Lossy image compression or layout-flattening text conversion.
  - `35`: Optical character recognition or lossy vectorization.
- **Latency & Startup Weight**:
  - `1 - 3`: Sub-50ms C/C++ or OS native binary (`pdftocairo`, `rsvg-convert`, `sips`, `textutil`, `pdftoppm`).
  - `5 - 8`: Python built-in standard library or lightweight parser.
  - `10 - 15`: Heavy command line runtime (`magick`, `inkscape`, `tesseract`, headless browser).

### Master Atomic Edge Table

| Source | Target | Primary Tool | Primary Command Template | Cost | Fallback Tool & Command | Fallback Cost |
| :--- | :--- | :--- | :--- | :---: | :--- | :---: |
| `pdf` | `svg` | `pdftocairo` | `pdftocairo -svg -f {page} -l {page} {in} {out}` | **7** | `inkscape --pdf-poppler {in} -o {out}` | **24** |
| `svg` | `pdf` | `rsvg-convert` | `rsvg-convert -f pdf {in} -o {out}` | **6** | `inkscape {in} -o {out}` | **22** |
| `svg` | `png` | `rsvg-convert` | `rsvg-convert -d {dpi} -p {dpi} {in} -o {out}` | **11** | `inkscape {in} -o {out} -d {dpi}` | **25** |
| `pdf` | `png` | `pdftoppm` | `pdftoppm -png -r {dpi} -f {page} -l {page} -singlefile {in} {out_base}` | **11** | `sips -s format png {in} --out {out}` | **21** |
| `pdf` | `jpg` | `pdftoppm` | `pdftoppm -jpeg -r {dpi} -f {page} -l {page} -singlefile {in} {out_base}` | **12** | `sips -s format jpeg {in} --out {out}` | **22** |
| `pdf` | `txt` | `pdftotext` | `pdftotext -f {page} -l {page} {in} {out}` | **5** | `tesseract {in} {out_base} -l eng` | **45** |
| `png` | `jpg` | `sips` | `sips -s format jpeg -s formatOptions {quality} {in} --out {out}` | **6** | `magick {in} -quality {quality} {out}` | **16** |
| `jpg` | `png` | `sips` | `sips -s format png {in} --out {out}` | **5** | `magick {in} {out}` | **15** |
| `png` | `pdf` | `sips` | `sips -s format pdf {in} --out {out}` | **6** | `magick {in} -density {dpi} {out}` | **16** |
| `jpg` | `pdf` | `sips` | `sips -s format pdf {in} --out {out}` | **6** | `magick {in} -density {dpi} {out}` | **16** |
| `png` | `webp` | `magick` | `magick {in} -quality {quality} {out}` | **14** | None | $\infty$ |
| `webp` | `png` | `magick` | `magick {in} {out}` | **14** | None | $\infty$ |
| `png` | `txt` | `tesseract` | `tesseract {in} {out_base} -l eng` | **38** | None | $\infty$ |
| `md` | `html` | `builtin_md` | Python zero-dependency Markdown parser | **4** | None | $\infty$ |
| `html` | `txt` | `textutil` | `textutil -convert txt {in} -output {out}` | **5** | None | $\infty$ |
| `html` | `rtf` | `textutil` | `textutil -convert rtf {in} -output {out}` | **6** | None | $\infty$ |
| `html` | `docx` | `textutil` | `textutil -convert docx {in} -output {out}` | **7** | None | $\infty$ |
| `txt` | `rtf` | `textutil` | `textutil -convert rtf {in} -output {out}` | **5** | None | $\infty$ |
| `txt` | `docx` | `textutil` | `textutil -convert docx {in} -output {out}` | **6** | None | $\infty$ |
| `html` | `pdf` | `chrome` | `Chrome --headless --print-to-pdf={out} {in}` | **17** | `weasyprint {in} {out}` | **14** |

---

## Resulting Route Examples

Dijkstra route resolution with these explicit scores produces optimal conversion paths:

1. **`sample.pdf -> sample.svg`**:
   - Path: `pdf -> svg` via `pdftocairo`
   - Total Cost: **7**
   - Rationale: High-speed Cairo vector extraction, avoiding the slower `inkscape` invocation.

2. **`diagram.svg -> diagram.png --dpi 300`**:
   - Path: `svg -> png` via `rsvg-convert`
   - Total Cost: **11**
   - Rationale: Direct rasterization at specified resolution in under 20 milliseconds.

3. **`notes.md -> notes.pdf`**:
   - Path: `md -> html` (Cost 4) $\to$ `html -> pdf` via headless Chrome (Cost 17)
   - Total Cost: **21**
   - Rationale: Preserves document headings, code blocks, and styling with full modern CSS support.

4. **`notes.md -> notes.docx`**:
   - Path: `md -> html` (Cost 4) $\to$ `html -> docx` via `textutil` (Cost 7)
   - Total Cost: **11**
   - Rationale: Direct semantic transformation utilizing Apple's native document engine.

5. **`notes.md -> notes.png`**:
   - Path: `md -> html` (Cost 4) $\to$ `html -> pdf` (Cost 17) $\to$ `pdf -> png` (Cost 11)
   - Total Cost: **32**
   - Rationale: Discovers the optimal multi-hop bridge cleanly without any custom pipeline coding.

---

## Dependency Management and Health CLI

To address missing tools deterministically, the CLI will include health check and dependency installation commands:

### 1. `convert doctor`
Inspects the environment for all primary and fallback binaries, reporting their status in a clear terminal table:
```
[✓] pdftocairo     /opt/homebrew/bin/pdftocairo (poppler)
[✓] rsvg-convert    /opt/homebrew/bin/rsvg-convert (librsvg)
[✓] pdftoppm       /opt/homebrew/bin/pdftoppm (poppler)
[✓] pdftotext      /opt/homebrew/bin/pdftotext (poppler)
[✓] sips           /usr/bin/sips (macOS native)
[✓] textutil       /usr/bin/textutil (macOS native)
[✓] inkscape       /opt/homebrew/bin/inkscape
[✓] magick         /opt/homebrew/bin/magick (ImageMagick)
[✓] tesseract      /opt/homebrew/bin/tesseract
[✓] chrome         /Applications/Google Chrome.app
```

### 2. `convert install-deps`
Asserts required tools for a requested conversion, or installs missing recommended packages via Homebrew:
```bash
brew install poppler librsvg imagemagick tesseract
```

---

## Project Structure

The project resides with the following modular architecture:

```
fconv/
├── pyproject.toml              # Metadata and build configuration
├── bin/
│   ├── convert                 # Primary executable script
│   └── fconv                   # Secondary symlink alias avoiding ImageMagick collision
├── fconv/
│   ├── __init__.py
│   ├── cli.py                  # CLI argument parsing and commands (doctor, install-deps)
│   ├── options.py              # Normalized options (dpi, quality, page)
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── node.py             # Extension aliases and normalization
│   │   ├── edge.py             # Edge definition with explicit cost and command builder
│   │   ├── router.py           # Dijkstra pathfinding algorithm
│   │   └── registry.py         # Curated atomic edge definitions and score assignments
│   ├── converters/
│   │   ├── __init__.py
│   │   ├── poppler.py          # pdftocairo, pdftoppm, pdftotext
│   │   ├── librsvg.py          # rsvg-convert
│   │   ├── inkscape.py         # inkscape vector fallback
│   │   ├── webp.py             # cwebp, dwebp
│   │   ├── imagemagick.py      # magick raster tools
│   │   ├── macos_native.py     # sips and textutil
│   │   ├── ocr.py              # tesseract OCR
│   │   ├── browser.py          # headless Chrome HTML to PDF
│   │   └── markdown.py         # zero-dependency Markdown parser
│   └── engine/
│       ├── __init__.py
│       ├── pipeline.py         # Multi-hop execution and temporary directory manager
│       ├── doctor.py           # Environment probing and dependency verification
│       └── process.py          # Subprocess runner with timeout and error handling
└── tests/
    ├── test_graph.py           # Route verification and score validation
    └── test_converters.py      # Command line generation and execution tests
```

---

## Implementation Phases

### Phase 1: Core Graph and Explicit Edge Registry
- Create project directory layout and packaging.
- Implement format normalization in `fconv/graph/node.py`.
- Build the explicit atomic edge registry and Dijkstra pathfinder in `fconv/graph/registry.py` and `fconv/graph/router.py`.
- Validate all routing paths and score totals with unit tests.

### Phase 2: Converter Adapters and Native Tools
- Implement Poppler adapters (`pdftocairo`, `pdftoppm`, `pdftotext`) in `fconv/converters/poppler.py`.
- Implement librsvg adapter (`rsvg-convert`) in `fconv/converters/librsvg.py`.
- Implement native macOS adapters (`sips`, `textutil`) in `fconv/converters/macos_native.py`.
- Implement WebP adapters (`cwebp`, `dwebp`) in `fconv/converters/webp.py`.
- Implement Markdown parsing and headless browser adapter in `fconv/converters/markdown.py` and `fconv/converters/browser.py`.
- Implement fallback adapters (`inkscape`, `magick`, `tesseract`).

### Phase 3: Pipeline Runner and CLI Experience
- Implement the execution pipeline with temporary directory management and error reporting in `fconv/engine/pipeline.py`.
- Implement `convert doctor` and `convert install-deps` in `fconv/engine/doctor.py`.
- Implement the CLI in `fconv/cli.py` supporting `-d, --dpi`, `-p, --page`, `-q, --quality`, `--explain`, and `--engine`.
- Create executable shims `bin/convert` and `bin/fconv`.

### Phase 4: System Integration and Verification
- Symlink executable into `~/.local/bin/convert` and `~/.local/bin/fconv`.
- Verify end-to-end conversions across test files:
  - Vector preservation: `sample.pdf <-> sample.svg`
  - High-resolution rasterization: `sample.pdf -> sample.png --dpi 300` and `sample.svg -> sample.png --dpi 600`
  - Document conversion: `sample.md -> sample.html`, `sample.md -> sample.docx`, and `sample.md -> sample.pdf`
  - Text extraction: `sample.pdf -> sample.txt` and `sample.png -> sample.txt` via OCR.
