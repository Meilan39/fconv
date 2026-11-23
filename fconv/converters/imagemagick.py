"""ImageMagick adapter: magick."""

from typing import List, Optional
from fconv.converters.base import ensure_parent_dir, is_tool_installed
from fconv.engine.process import run_process
from fconv.options import ConvertOptions


def has_magick() -> bool:
    return is_tool_installed("magick")


def build_magick_cmd(
    src: str,
    dst: str,
    opts: ConvertOptions,
    source_fmt: Optional[str] = None,
    target_fmt: Optional[str] = None,
) -> List[str]:
    cmd = ["magick"]
    if source_fmt == "pdf":
        dpi = opts.dpi if opts.dpi is not None else 300
        cmd.extend(["-density", str(dpi)])
        page_idx = (opts.page or 1) - 1
        cmd.append(f"{src}[{page_idx}]")
    else:
        if opts.dpi is not None:
            cmd.extend(["-density", str(opts.dpi)])
        cmd.append(src)

    if target_fmt == "jpg":
        cmd.extend(["-background", "white", "-alpha", "remove", "-alpha", "off"])

    if opts.quality is not None:
        cmd.extend(["-quality", str(opts.quality)])

    cmd.append(dst)
    return cmd


def convert_magick(
    src: str,
    dst: str,
    opts: ConvertOptions,
    source_fmt: Optional[str] = None,
    target_fmt: Optional[str] = None,
) -> None:
    ensure_parent_dir(dst)
    cmd = build_magick_cmd(src, dst, opts, source_fmt=source_fmt, target_fmt=target_fmt)
    run_process(cmd, timeout=opts.timeout, verbose=opts.verbose)
