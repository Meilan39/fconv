"""ImageMagick adapter: magick."""

from typing import List
from fconv.converters.base import ensure_parent_dir, is_tool_installed
from fconv.engine.process import run_process
from fconv.options import ConvertOptions


def has_magick() -> bool:
    return is_tool_installed("magick")


def build_magick_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    cmd = ["magick"]
    if opts.dpi is not None:
        cmd.extend(["-density", str(opts.dpi)])
    cmd.append(src)
    if opts.quality is not None:
        cmd.extend(["-quality", str(opts.quality)])
    cmd.append(dst)
    return cmd


def convert_magick(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    cmd = build_magick_cmd(src, dst, opts)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
