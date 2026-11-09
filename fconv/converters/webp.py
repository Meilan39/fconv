"""WebP adapter using official cwebp and dwebp utilities."""

from typing import List
from fconv.converters.base import ensure_parent_dir, is_tool_installed
from fconv.engine.process import run_process
from fconv.options import ConvertOptions


def has_cwebp() -> bool:
    return is_tool_installed("cwebp")


def has_dwebp() -> bool:
    return is_tool_installed("dwebp")


def build_cwebp_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    quality = opts.quality if opts.quality is not None else 80
    return ["cwebp", "-q", str(quality), src, "-o", dst]


def convert_image_to_webp(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_cwebp_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)


def build_dwebp_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    return ["dwebp", src, "-o", dst]


def convert_webp_to_image(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_dwebp_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
