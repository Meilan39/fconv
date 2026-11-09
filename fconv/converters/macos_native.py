"""macOS native adapters: sips and textutil."""

from typing import List
from fconv.converters.base import ensure_parent_dir, is_tool_installed
from fconv.engine.process import run_process
from fconv.options import ConvertOptions


def has_sips() -> bool:
    return is_tool_installed("sips")


def has_textutil() -> bool:
    return is_tool_installed("textutil")


# --- sips: Image & PDF wrappers ---

def _format_for_sips(fmt: str) -> str:
    mapping = {
        "jpg": "jpeg",
        "jpeg": "jpeg",
        "png": "png",
        "pdf": "pdf",
        "tiff": "tiff",
        "bmp": "bmp",
        "gif": "gif",
    }
    return mapping.get(fmt.lower(), fmt.lower())


def build_sips_cmd(src: str, dst: str, target_fmt: str, opts: ConvertOptions) -> List[str]:
    sips_fmt = _format_for_sips(target_fmt)
    cmd = ["sips", "-s", "format", sips_fmt]
    if sips_fmt == "jpeg" and opts.quality is not None:
        cmd.extend(["-s", "formatOptions", str(opts.quality)])
    cmd.extend([src, "--out", dst])
    return cmd


def convert_image_sips(src: str, dst: str, target_fmt: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_sips_cmd(src, dst, target_fmt, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)


# --- textutil: Document conversions ---

def _format_for_textutil(fmt: str) -> str:
    mapping = {
        "txt": "txt",
        "text": "txt",
        "html": "html",
        "htm": "html",
        "rtf": "rtf",
        "docx": "docx",
    }
    return mapping.get(fmt.lower(), fmt.lower())


def build_textutil_cmd(src: str, dst: str, target_fmt: str, opts: ConvertOptions) -> List[str]:
    tu_fmt = _format_for_textutil(target_fmt)
    return ["textutil", "-convert", tu_fmt, src, "-output", dst]


def convert_doc_textutil(src: str, dst: str, target_fmt: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_textutil_cmd(src, dst, target_fmt, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
