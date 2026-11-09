"""librsvg adapter: rsvg-convert."""

from typing import List
from fconv.converters.base import ensure_parent_dir, is_tool_installed
from fconv.engine.process import run_process
from fconv.options import ConvertOptions


def has_rsvg_convert() -> bool:
    return is_tool_installed("rsvg-convert")


# --- SVG -> PDF ---

def build_svg_to_pdf_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    cmd = ["rsvg-convert", "-f", "pdf"]
    if opts.dpi is not None:
        cmd.extend(["-d", str(opts.dpi), "-p", str(opts.dpi)])
    cmd.extend(["-o", dst, src])
    return cmd


def convert_svg_to_pdf(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_svg_to_pdf_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)


# --- SVG -> PNG ---

def build_svg_to_png_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    dpi = str(opts.dpi or 300)
    cmd = ["rsvg-convert", "-f", "png", "-d", dpi, "-p", dpi, "-o", dst, src]
    return cmd


def convert_svg_to_png(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_svg_to_png_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
