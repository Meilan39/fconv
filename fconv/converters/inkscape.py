"""Inkscape adapter for vector fallback operations."""

from typing import List
from fconv.converters.base import ensure_parent_dir, is_tool_installed
from fconv.engine.process import run_process
from fconv.options import ConvertOptions


def has_inkscape() -> bool:
    return is_tool_installed("inkscape")


# --- PDF -> SVG ---

def build_pdf_to_svg_inkscape_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    cmd = ["inkscape", "--pdf-poppler"]
    page = opts.page or 1
    cmd.append(f"--pages={page}")
    cmd.extend(["-o", dst, src])
    return cmd


def convert_pdf_to_svg_inkscape(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_pdf_to_svg_inkscape_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)


# --- SVG -> PDF ---

def build_svg_to_pdf_inkscape_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    return ["inkscape", "-o", dst, src]


def convert_svg_to_pdf_inkscape(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_svg_to_pdf_inkscape_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)


# --- SVG -> PNG ---

def build_svg_to_png_inkscape_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    cmd = ["inkscape", "-o", dst]
    if opts.dpi is not None:
        cmd.extend(["-d", str(opts.dpi)])
    cmd.append(src)
    return cmd


def convert_svg_to_png_inkscape(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_svg_to_png_inkscape_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
