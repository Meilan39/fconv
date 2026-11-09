"""Tesseract OCR adapter for raster images and scanned documents."""

import os
import shutil
from typing import List
from fconv.converters.base import ensure_parent_dir, is_tool_installed
from fconv.engine.process import run_process
from fconv.options import ConvertOptions


def has_tesseract() -> bool:
    return is_tool_installed("tesseract")


def _get_ocr_root(dst: str) -> str:
    if dst.lower().endswith(".txt"):
        return dst[:-4]
    return dst


def build_tesseract_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    root = _get_ocr_root(dst)
    return ["tesseract", src, root, "-l", "eng"]


def convert_image_to_txt_ocr(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    root = _get_ocr_root(dst)
    cmd = build_tesseract_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout * 2, verbose=opts.verbose)
    expected_output = f"{root}.txt"
    if expected_output != dst and os.path.exists(expected_output):
        shutil.move(expected_output, dst)
