"""Poppler adapters: pdftocairo, pdftoppm, and pdftotext."""

import os
import shutil
from typing import List
from fconv.converters.base import ensure_parent_dir, is_tool_installed
from fconv.engine.process import run_process
from fconv.options import ConvertOptions


def has_pdftocairo() -> bool:
    return is_tool_installed("pdftocairo")


def has_pdftoppm() -> bool:
    return is_tool_installed("pdftoppm")


def has_pdftotext() -> bool:
    return is_tool_installed("pdftotext")


# --- pdftocairo: PDF -> SVG ---

def build_pdf_to_svg_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    page = opts.page or 1
    return ["pdftocairo", "-svg", "-f", str(page), "-l", str(page), src, dst]


def convert_pdf_to_svg(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_pdf_to_svg_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)


# --- pdftoppm: PDF -> PNG / JPG / TIFF ---

def _get_ppm_root(dst: str, ext: str) -> str:
    """Strip extension from dst to provide the PPM root path."""
    if dst.lower().endswith(ext):
        return dst[:-len(ext)]
    return dst


def build_pdf_to_png_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    root = _get_ppm_root(dst, ".png")
    dpi = str(opts.dpi if opts.dpi is not None else 300)
    cmd = ["pdftoppm", "-png", "-r", dpi, "-singlefile"]
    page = opts.page or 1
    cmd.extend(["-f", str(page), "-l", str(page)])
    cmd.extend([src, root])
    return cmd


def convert_pdf_to_png(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    root = _get_ppm_root(dst, ".png")
    cmd = build_pdf_to_png_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
    expected_output = f"{root}.png"
    if os.path.abspath(expected_output) != os.path.abspath(dst) and os.path.exists(expected_output):
        shutil.move(expected_output, dst)


def build_pdf_to_jpg_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    ext = ".jpeg" if dst.lower().endswith(".jpeg") else ".jpg"
    root = _get_ppm_root(dst, ext)
    dpi = str(opts.dpi if opts.dpi is not None else 300)
    cmd = ["pdftoppm", "-jpeg", "-r", dpi, "-singlefile"]
    if opts.quality is not None:
        cmd.extend(["-jpegopt", f"quality={opts.quality}"])
    page = opts.page or 1
    cmd.extend(["-f", str(page), "-l", str(page)])
    cmd.extend([src, root])
    return cmd


def convert_pdf_to_jpg(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    ext = ".jpeg" if dst.lower().endswith(".jpeg") else ".jpg"
    root = _get_ppm_root(dst, ext)
    cmd = build_pdf_to_jpg_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
    expected_output = f"{root}.jpg"
    if not os.path.exists(expected_output):
        expected_output = f"{root}.jpeg"
    if os.path.abspath(expected_output) != os.path.abspath(dst) and os.path.exists(expected_output):
        shutil.move(expected_output, dst)


def build_pdf_to_tiff_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    ext = ".tiff" if dst.lower().endswith(".tiff") else ".tif"
    root = _get_ppm_root(dst, ext)
    dpi = str(opts.dpi if opts.dpi is not None else 300)
    cmd = ["pdftoppm", "-tiff", "-r", dpi, "-singlefile"]
    page = opts.page or 1
    cmd.extend(["-f", str(page), "-l", str(page)])
    cmd.extend([src, root])
    return cmd


def convert_pdf_to_tiff(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    ext = ".tiff" if dst.lower().endswith(".tiff") else ".tif"
    root = _get_ppm_root(dst, ext)
    cmd = build_pdf_to_tiff_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
    expected_output = f"{root}.tif"
    if not os.path.exists(expected_output):
        expected_output = f"{root}.tiff"
    if os.path.abspath(expected_output) != os.path.abspath(dst) and os.path.exists(expected_output):
        shutil.move(expected_output, dst)


# --- pdftotext: PDF -> TXT ---

def build_pdf_to_txt_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    cmd = ["pdftotext", "-layout"]
    if opts.page is not None:
        cmd.extend(["-f", str(opts.page), "-l", str(opts.page)])
    cmd.extend([src, dst])
    return cmd


def convert_pdf_to_txt(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_pdf_to_txt_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
