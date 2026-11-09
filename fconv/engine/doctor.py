"""Environment diagnostics and dependency installation helpers."""

import shutil
from typing import Dict, List, Tuple
from fconv.converters.browser import find_browser_binary


TOOLS_SPEC: List[Tuple[str, str, str, str]] = [
    # (name, package, category, check_target)
    ("pdftocairo", "poppler", "Core Vector (PDF -> SVG)", "pdftocairo"),
    ("pdftoppm", "poppler", "Core Raster (PDF -> PNG/JPG)", "pdftoppm"),
    ("pdftotext", "poppler", "Core Text (PDF -> TXT)", "pdftotext"),
    ("sips", "macOS Native", "Native Image Core (PNG/JPG/PDF)", "sips"),
    ("textutil", "macOS Native", "Native Document Core (HTML/TXT/DOCX)", "textutil"),
    ("cwebp", "webp", "WebP Encoder (Image -> WebP)", "cwebp"),
    ("dwebp", "webp", "WebP Decoder (WebP -> Image)", "dwebp"),
    ("inkscape", "inkscape", "Core Vector (SVG <-> PDF)", "inkscape"),
    ("chrome", "Google Chrome", "HTML -> PDF Engine", "browser"),
]


def check_all_tools() -> List[Dict[str, str]]:
    """Inspect system and return status dictionary for all supported tools."""
    results = []
    for name, pkg, cat, check_target in TOOLS_SPEC:
        if check_target == "browser":
            path = find_browser_binary()
        else:
            path = shutil.which(check_target)

        status = "Installed" if path else "Missing"
        results.append({
            "name": name,
            "package": pkg,
            "category": cat,
            "path": path or "-",
            "status": status,
            "available": bool(path),
        })
    return results


def run_doctor() -> None:
    """Print formatted system diagnostic report."""
    results = check_all_tools()
    print("\n=== File Converter System Doctor ===")
    print(f"{'Tool':<15} {'Status':<12} {'Package':<16} {'Path'}")
    print("-" * 75)

    all_ok = True
    missing_homebrew = set()

    for item in results:
        marker = "[✓]" if item["available"] else "[✗]"
        status_str = f"{marker} {item['status']}"
        print(f"{item['name']:<15} {status_str:<12} {item['package']:<16} {item['path']}")
        if not item["available"]:
            all_ok = False
            if item["package"] not in ("macOS Native", "Google Chrome"):
                missing_homebrew.add(item["package"])

    print("-" * 75)
    if all_ok:
        print("All conversion engines are fully operational on this system.")
    else:
        print("Some optional engines are missing.")
        if missing_homebrew:
            pkgs = " ".join(sorted(missing_homebrew))
            print(f"\nTo install missing CLI packages via Homebrew:\n  brew install {pkgs}")


def run_install_deps() -> None:
    """Print Homebrew installation command for all external conversion dependencies."""
    homebrew_packages = ["poppler", "librsvg", "imagemagick", "tesseract"]
    print("\nRecommended dependencies for maximum format coverage:")
    print(f"  brew install {' '.join(homebrew_packages)}")
    print("\nNote: sips and textutil are pre-installed by macOS.")
    print("Google Chrome provides HTML to PDF conversion if installed under /Applications.")
