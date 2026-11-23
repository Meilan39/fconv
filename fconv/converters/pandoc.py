"""Pandoc adapter for Markdown, HTML, DOCX, RTF, TXT, and LaTeX PDF conversions."""

import html
import os
from pathlib import Path
import tempfile
from typing import Dict, List, Optional
from fconv.converters.base import ensure_parent_dir, is_tool_installed
from fconv.engine.process import ProcessExecutionError, resolve_binary, run_process
from fconv.options import ConvertOptions

# TeX engines supporting -V geometry:margin and -V fontsize
TEX_PDF_ENGINES = ("xelatex", "pdflatex", "lualatex", "tectonic")
MACOS_TEXBIN_DIR = "/Library/TeX/texbin"

PANDOC_MD_FORMAT = (
    "markdown+tex_math_dollars+tex_math_single_backslash+tex_math_double_backslash"
    "+pipe_tables+fenced_code_blocks+strikeout+task_lists-subscript-superscript"
)

_PANDOC_INPUT_FORMATS: Dict[str, str] = {
    "md": PANDOC_MD_FORMAT,
    "html": "html",
    "docx": "docx",
    "rtf": "rtf",
}

_PANDOC_OUTPUT_FORMATS: Dict[str, str] = {
    "md": "gfm",
    "txt": "plain",
    "html": "html5",
    "docx": "docx",
    "rtf": "rtf",
}

PANDOC_HTML_STYLE_HEADER = """<style>
  @page {
    size: letter;
    margin: 12mm 14mm;
  }
  html {
    max-width: none;
    margin: 0;
    padding: 0;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: #24292e;
    max-width: 860px;
    margin: 40px auto;
    padding: 0 20px;
  }
  h1, h2, h3, h4, h5, h6 {
    margin-top: 22px;
    margin-bottom: 12px;
    font-weight: 600;
    line-height: 1.25;
  }
  h1 { font-size: 1.9em; border-bottom: 1px solid #eaecef; padding-bottom: 0.25em; }
  h2 { font-size: 1.45em; border-bottom: 1px solid #eaecef; padding-bottom: 0.25em; }
  h3 { font-size: 1.2em; }
  p, blockquote, ul, ol, dl, table, pre {
    margin-top: 0;
    margin-bottom: 14px;
  }
  code {
    background-color: #f6f8fa;
    border-radius: 3px;
    font-size: 88%;
    padding: 0.15em 0.35em;
    font-family: SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  }
  pre {
    background-color: #f6f8fa;
    border-radius: 6px;
    font-size: 88%;
    line-height: 1.45;
    overflow-x: auto;
    padding: 12px 14px;
  }
  pre code {
    background-color: transparent;
    padding: 0;
  }
  blockquote {
    padding: 0 1em;
    color: #57606a;
    border-left: 0.25em solid #dfe2e5;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 14px 0;
  }
  table th, table td {
    padding: 6px 11px;
    border: 1px solid #dfe2e5;
  }
  table tr:nth-child(2n) {
    background-color: #f6f8fa;
  }
  img {
    max-width: 100%;
    box-sizing: content-box;
  }
  math[display="block"] {
    margin: 12px 0;
    font-size: 1.05em;
  }
  @media print {
    body {
      margin: 0;
      padding: 0;
      max-width: none;
      font-size: 11pt;
    }
    pre {
      white-space: pre-wrap;
      word-wrap: break-word;
      break-inside: avoid;
    }
    blockquote, table tr, img {
      break-inside: avoid;
    }
    h1, h2, h3, h4, h5, h6 {
      break-after: avoid;
    }
  }
</style>
"""


def has_pandoc() -> bool:
    """Return True if the pandoc CLI binary is available."""
    return is_tool_installed("pandoc")


def find_pdf_engine() -> Optional[str]:
    """Find an available LaTeX PDF engine for Pandoc."""
    for engine in TEX_PDF_ENGINES:
        found = resolve_binary(engine)
        if found:
            return found
        mactex_path = os.path.join(MACOS_TEXBIN_DIR, engine)
        if os.path.isfile(mactex_path) and os.access(mactex_path, os.X_OK):
            return mactex_path
    return None


def has_pandoc_pdf() -> bool:
    """Return True if both pandoc and a supported PDF engine are available."""
    return has_pandoc() and find_pdf_engine() is not None


def _has_tex_package(sty_name: str) -> bool:
    """Return True if a LaTeX package file is discoverable via kpsewhich."""
    kpse = resolve_binary("kpsewhich")
    if not kpse:
        return True
    try:
        res = run_process([kpse, sty_name], timeout=5)
        return bool(res.stdout.strip())
    except ProcessExecutionError:
        return False


def _safe_latex_md_format() -> str:
    """Adjust Pandoc Markdown extensions when optional TeX packages are missing."""
    if _has_tex_package("soul.sty"):
        return PANDOC_MD_FORMAT
    return PANDOC_MD_FORMAT.replace("+strikeout", "-strikeout")


def _source_resource_dir(src: str) -> str:
    """Return directory containing src for --resource-path and <base href>."""
    return os.path.dirname(os.path.abspath(src)) or "."


def build_md_to_html_pandoc_cmd(
    src: str,
    dst: str,
    opts: ConvertOptions,
    header_file: Optional[str] = None,
) -> List[str]:
    """Construct Pandoc CLI arguments for Markdown to standalone HTML5 with offline MathML."""
    pagetitle = os.path.splitext(os.path.basename(src))[0] or "Converted Document"
    src_dir = _source_resource_dir(src)
    cmd = [
        "pandoc",
        src,
        "-f",
        PANDOC_MD_FORMAT,
        "-t",
        "html5",
        "--standalone",
        "--math-method=mathml",
        "--metadata",
        f"pagetitle={pagetitle}",
        "--resource-path",
        src_dir,
    ]
    if header_file:
        cmd.extend(["-H", header_file])
    cmd.extend(["-o", dst])
    return cmd


def convert_md_to_html_pandoc(src: str, dst: str, opts: ConvertOptions) -> None:
    """Convert Markdown to styled standalone HTML5 with native MathML via Pandoc."""
    ensure_parent_dir(dst)
    base_uri = html.escape(Path(_source_resource_dir(src)).as_uri() + "/", quote=True)
    with tempfile.TemporaryDirectory(prefix="fconv_pandoc_") as temp_dir:
        header_path = os.path.join(temp_dir, "head.html")
        with open(header_path, "w", encoding="utf-8") as f:
            f.write(f'<base href="{base_uri}">\n')
            f.write(PANDOC_HTML_STYLE_HEADER)
        cmd = build_md_to_html_pandoc_cmd(src, dst, opts, header_file=header_path)
        run_process(cmd, timeout=opts.timeout * 2, verbose=opts.verbose)


def build_md_to_pdf_pandoc_cmd(src: str, dst: str, opts: ConvertOptions) -> List[str]:
    """Construct Pandoc CLI arguments for Markdown to PDF via a LaTeX engine."""
    return build_to_pdf_pandoc_cmd(src, dst, "md", opts)


def build_to_pdf_pandoc_cmd(src: str, dst: str, src_fmt: str, opts: ConvertOptions) -> List[str]:
    """Construct Pandoc CLI arguments to typeset a document to PDF via LaTeX."""
    engine = find_pdf_engine() or "xelatex"
    in_fmt = _safe_latex_md_format() if src_fmt == "md" else _PANDOC_INPUT_FORMATS.get(src_fmt, src_fmt)
    src_dir = _source_resource_dir(src)
    return [
        "pandoc",
        src,
        "-f",
        in_fmt,
        "-t",
        "pdf",
        "-o",
        dst,
        f"--pdf-engine={engine}",
        "--resource-path",
        src_dir,
        "-V",
        "geometry:margin=0.75in",
        "-V",
        "fontsize=11pt",
        "-V",
        "linestretch=1.15",
        "-V",
        "colorlinks=true",
    ]


def convert_md_to_pdf_pandoc(src: str, dst: str, opts: ConvertOptions) -> None:
    """Convert Markdown directly to PDF via Pandoc and an installed TeX engine."""
    convert_to_pdf_pandoc(src, dst, "md", opts)


def convert_to_pdf_pandoc(src: str, dst: str, src_fmt: str, opts: ConvertOptions) -> None:
    """Convert a supported document directly to PDF via Pandoc and TeX."""
    ensure_parent_dir(dst)
    cmd = build_to_pdf_pandoc_cmd(src, dst, src_fmt, opts)
    run_process(cmd, timeout=opts.timeout * 2, verbose=opts.verbose)


def build_pandoc_doc_cmd(
    src: str,
    dst: str,
    src_fmt: str,
    dst_fmt: str,
    opts: ConvertOptions,
) -> List[str]:
    """Construct Pandoc CLI arguments for document format conversions."""
    in_fmt = _PANDOC_INPUT_FORMATS.get(src_fmt, src_fmt)
    out_fmt = _PANDOC_OUTPUT_FORMATS.get(dst_fmt, dst_fmt)
    cmd = [
        "pandoc",
        src,
        "-f",
        in_fmt,
        "-t",
        out_fmt,
    ]
    if dst_fmt in ("html", "rtf"):
        cmd.append("--standalone")
    if src_fmt in ("md", "html"):
        cmd.extend(["--resource-path", _source_resource_dir(src)])
    cmd.extend(["-o", dst])
    return cmd


def convert_doc_pandoc(
    src: str,
    dst: str,
    src_fmt: str,
    dst_fmt: str,
    opts: ConvertOptions,
) -> None:
    """Convert between text/document formats using Pandoc."""
    ensure_parent_dir(dst)
    cmd = build_pandoc_doc_cmd(src, dst, src_fmt, dst_fmt, opts)
    run_process(cmd, timeout=opts.timeout * 2, verbose=opts.verbose)
