"""Environment diagnostics and dependency installation helpers."""

import sys
from typing import Any, Dict, List, Optional, Tuple
from fconv.converters.browser import find_browser_binary
from fconv.converters.pandoc import find_pdf_engine
from fconv.engine.process import resolve_binary


TOOLS_SPEC: List[Tuple[str, str, str, str]] = [
    # (name, package, category, check_target)
    ("pdftocairo", "poppler", "Core Vector (PDF -> SVG)", "pdftocairo"),
    ("pdftoppm", "poppler", "Core Raster (PDF -> PNG/JPG/TIFF)", "pdftoppm"),
    ("pdftotext", "poppler", "Core Text (PDF -> TXT)", "pdftotext"),
    ("rsvg-convert", "librsvg", "Core Vector (SVG -> PDF/PNG)", "rsvg-convert"),
    ("inkscape", "inkscape", "Vector Fallback (PDF <-> SVG / PNG)", "inkscape"),
    ("sips", "macOS Native", "Native Image Core (PNG/JPG/TIFF/BMP/GIF/PDF)", "sips"),
    ("textutil", "macOS Native", "Native Document Core (HTML/TXT/RTF/DOCX)", "textutil"),
    ("cwebp", "webp", "WebP Encoder (PNG/JPG/TIFF -> WebP)", "cwebp"),
    ("dwebp", "webp", "WebP Decoder (WebP -> PNG/TIFF/BMP)", "dwebp"),
    ("magick", "imagemagick", "Cross-Platform Raster & PDF Fallback", "magick"),
    ("tesseract", "tesseract", "OCR Engine (PNG/JPG/TIFF -> TXT)", "tesseract"),
    ("pandoc", "pandoc", "Markdown & Document Core", "pandoc"),
    ("tex-engine", "basictex/tectonic", "LaTeX PDF Backend (Pandoc Fallback)", "tex_engine"),
    ("chrome", "Google Chrome", "HTML -> PDF Engine", "browser"),
]


def check_all_tools() -> List[Dict[str, Any]]:
    """Inspect system and return status dictionary for all supported tools."""
    results: List[Dict[str, Any]] = []
    for name, pkg, cat, check_target in TOOLS_SPEC:
        if pkg == "macOS Native" and sys.platform != "darwin":
            results.append({
                "name": name,
                "package": pkg,
                "category": cat,
                "path": "-",
                "status": "macOS-only",
                "available": False,
                "platform_skipped": True,
            })
            continue

        path: Optional[str]
        if check_target == "browser":
            path = find_browser_binary()
        elif check_target == "tex_engine":
            path = find_pdf_engine()
        else:
            path = resolve_binary(check_target)

        status = "Installed" if path else "Missing"
        results.append({
            "name": name,
            "package": pkg,
            "category": cat,
            "path": path or "-",
            "status": status,
            "available": bool(path),
            "platform_skipped": False,
        })
    return results


def run_doctor() -> None:
    """Print formatted system diagnostic report."""
    results = check_all_tools()
    print("\n=== File Converter System Doctor ===")
    print(f"{'Tool':<15} {'Status':<16} {'Package':<18} {'Path'}")
    print("-" * 80)

    all_ok = True
    missing_homebrew = set()

    for item in results:
        if item.get("platform_skipped"):
            marker = "[-]"
        else:
            marker = "[✓]" if item["available"] else "[✗]"
        status_str = f"{marker} {item['status']}"
        print(f"{item['name']:<15} {status_str:<16} {item['package']:<18} {item['path']}")
        if not item["available"] and not item.get("platform_skipped"):
            all_ok = False
            if item["package"] not in ("macOS Native", "Google Chrome", "basictex/tectonic"):
                missing_homebrew.add(item["package"])

    print("-" * 80)
    if all_ok:
        print("All conversion engines are fully operational on this system.")
    else:
        print("Some optional engines are missing.")
        if missing_homebrew:
            pkgs = " ".join(sorted(missing_homebrew))
            print(f"\nTo install missing CLI packages via Homebrew:\n  brew install {pkgs}")
        if any(i["name"] == "tex-engine" and not i["available"] for i in results):
            print(
                "\nFor optional LaTeX PDF fallback (--engine pandoc-latex):\n"
                "  brew install tectonic   # or: brew install --cask basictex"
            )


def run_install_deps() -> None:
    """Print Homebrew installation command for all external conversion dependencies."""
    homebrew_packages = ["poppler", "librsvg", "webp", "imagemagick", "inkscape", "tesseract", "pandoc"]
    print("\nRecommended dependencies for maximum format coverage:")
    print(f"  brew install {' '.join(homebrew_packages)}")
    print("\nOptional LaTeX PDF engine for --engine pandoc-latex fallback:")
    print("  brew install tectonic   # or: brew install --cask basictex")
    print("\nNote: sips and textutil are pre-installed by macOS.")
    print("Google Chrome (or Chromium/Brave) provides HTML -> PDF and primary MD -> PDF rendering.")
