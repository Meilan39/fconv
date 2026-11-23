"""Headless browser adapter for HTML to PDF rendering."""

import os
from pathlib import Path
import shutil
import tempfile
from typing import List, Optional
from fconv.converters.base import ensure_parent_dir
from fconv.engine.process import resolve_binary, run_process
from fconv.options import ConvertOptions

# Cross-platform browser candidates
BROWSER_CANDIDATES = [
    # System macOS paths
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    # User macOS paths
    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    os.path.expanduser("~/Applications/Chromium.app/Contents/MacOS/Chromium"),
    os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
    # Standard PATH binaries and Linux paths
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "brave",
    "brave-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
]


def find_browser_binary() -> Optional[str]:
    """Find installed headless browser executable across system paths."""
    for candidate in BROWSER_CANDIDATES:
        if candidate.startswith("/"):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        else:
            found = resolve_binary(candidate) or shutil.which(candidate)
            if found:
                return found
    return None


def has_browser() -> bool:
    return find_browser_binary() is not None


def build_browser_pdf_cmd(src: str, dst: str, opts: ConvertOptions, user_data_dir: str) -> List[str]:
    browser_bin = find_browser_binary() or "google-chrome"
    file_uri = Path(os.path.abspath(src)).as_uri()
    abs_dst = os.path.abspath(dst)
    cmd = [
        browser_bin,
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        f"--user-data-dir={user_data_dir}",
        "--virtual-time-budget=3000",
        "--no-pdf-header-footer",
        f"--print-to-pdf={abs_dst}",
        file_uri,
    ]
    return cmd


def convert_html_to_pdf_browser(src: str, dst: str, opts: ConvertOptions) -> None:
    if not find_browser_binary():
        raise RuntimeError("No compatible headless browser (Google Chrome, Chromium, Brave) found.")
    ensure_parent_dir(dst)
    with tempfile.TemporaryDirectory(prefix="fconv_chrome_") as temp_profile:
        cmd = build_browser_pdf_cmd(src, dst, opts, user_data_dir=temp_profile)
        run_process(cmd, timeout=opts.timeout * 2, verbose=opts.verbose)
