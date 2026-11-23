"""Zero-dependency Markdown parser and HTML generator."""

import html
import os
from pathlib import Path
import re
from typing import List, Optional
from fconv.converters.base import ensure_parent_dir
from fconv.options import ConvertOptions


KATEX_HEAD_SNIPPET = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
<script>
  document.addEventListener("DOMContentLoaded", function () {
    if (typeof renderMathInElement === "function") {
      renderMathInElement(document.body, {
        delimiters: [
          {left: "$$", right: "$$", display: true},
          {left: "\\[", right: "\\]", display: true},
          {left: "$", right: "$", display: false},
          {left: "\\(", right: "\\)", display: false}
        ],
        throwOnError: false
      });
    }
  });
</script>
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{base_tag}<title>Converted Document</title>
<style>
  @page {{
    size: letter;
    margin: 12mm 14mm;
  }}
  html {{
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: #24292e;
    max-width: 860px;
    margin: 40px auto;
    padding: 0 20px;
  }}
  h1, h2, h3, h4, h5, h6 {{
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
  }}
  h1 {{ font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
  h2 {{ font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
  h3 {{ font-size: 1.25em; }}
  p, blockquote, ul, ol, dl, table, pre {{
    margin-top: 0;
    margin-bottom: 16px;
  }}
  code {{
    background-color: #f6f8fa;
    border-radius: 3px;
    font-size: 88%;
    padding: 0.2em 0.4em;
    font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
  }}
  pre {{
    background-color: #f6f8fa;
    border-radius: 6px;
    font-size: 88%;
    line-height: 1.45;
    overflow: auto;
    padding: 16px;
  }}
  pre code {{
    background-color: transparent;
    padding: 0;
  }}
  blockquote {{
    padding: 0 1em;
    color: #6a737d;
    border-left: 0.25em solid #dfe2e5;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 16px;
  }}
  table th, table td {{
    padding: 6px 13px;
    border: 1px solid #dfe2e5;
  }}
  table tr:nth-child(2n) {{
    background-color: #f6f8fa;
  }}
  hr {{
    height: 0.25em;
    padding: 0;
    margin: 24px 0;
    background-color: #e1e4e8;
    border: 0;
  }}
  img {{
    max-width: 100%;
    box-sizing: content-box;
  }}
  .math-display {{
    margin: 16px 0;
    overflow-x: auto;
  }}
  @media print {{
    body {{
      margin: 0;
      padding: 0;
      max-width: none;
      font-size: 11pt;
    }}
    pre {{
      white-space: pre-wrap;
      word-wrap: break-word;
      break-inside: avoid;
    }}
    blockquote, table tr, img, .math-display {{
      break-inside: avoid;
    }}
    h1, h2, h3, h4, h5, h6 {{
      break-after: avoid;
    }}
  }}
</style>{head_extra}
</head>
<body>
{content}
</body>
</html>
"""


_INLINE_MATH_RE = re.compile(
    r"(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\(.+?\\\)|(?<!\\)\$(?!\s)([^$\n]+?)(?<!\s|\\)\$(?!\d))"
)


def contains_math(md_text: str) -> bool:
    """Return True if Markdown contains TeX math delimiters outside code blocks."""
    in_code_block = False
    for line in md_text.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        without_inline_code = re.sub(r"`[^`]+`", "", line)
        if (
            "$$" in without_inline_code
            or r"\(" in without_inline_code
            or r"\[" in without_inline_code
            or _INLINE_MATH_RE.search(without_inline_code)
        ):
            return True
    return False


def _inline_markdown_to_html(text: str) -> str:
    """Transform inline markdown elements to HTML while preserving code and math spans."""
    # Escape HTML special characters first
    text = html.escape(text)

    placeholders: List[str] = []

    def _stash(replacement: str) -> str:
        idx = len(placeholders)
        placeholders.append(replacement)
        return f"\x00PH{idx}\x00"

    # Protect inline code first so underscores/asterisks/math inside backticks stay literal
    text = re.sub(r"`([^`]+)`", lambda m: _stash(f"<code>{m.group(1)}</code>"), text)

    # Protect inline and display math spans from emphasis/link regexes
    text = _INLINE_MATH_RE.sub(lambda m: _stash(m.group(0)), text)

    # Images: ![alt](url)
    text = re.sub(r"!\[(.*?)\]\((.*?)\)", r'<img src="\2" alt="\1">', text)

    # Links: [text](url)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', text)

    # Bold: **text** or __text__ (underscore variant requires non-word boundaries for snake_case)
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"<strong>\1</strong>", text)

    # Italic: *text* or _text_ (underscore variant requires non-word boundaries for snake_case)
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)

    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.*?)~~", r"<del>\1</del>", text)

    # Restore stashed code and math spans
    for idx, value in enumerate(placeholders):
        text = text.replace(f"\x00PH{idx}\x00", value)

    return text


def parse_markdown_to_html(md_text: str) -> str:
    """Convert Markdown string to HTML body content."""
    lines = md_text.splitlines()
    output_lines: List[str] = []
    in_code_block = False
    code_block_lines: List[str] = []
    math_block_delim: Optional[str] = None
    math_block_lines: List[str] = []
    in_list = False
    list_type = "ul"
    in_table = False
    paragraph_lines: List[str] = []

    def _flush_paragraph() -> None:
        if paragraph_lines:
            joined = " ".join(paragraph_lines)
            output_lines.append(f"<p>{_inline_markdown_to_html(joined)}</p>")
            paragraph_lines.clear()

    def _flush_list() -> None:
        nonlocal in_list
        if in_list:
            output_lines.append(f"</{list_type}>")
            in_list = False

    def _flush_table() -> None:
        nonlocal in_table
        if in_table:
            output_lines.append("</tbody></table>")
            in_table = False

    for line in lines:
        stripped = line.strip()

        # Fenced code blocks
        if math_block_delim is None and stripped.startswith("```"):
            if in_code_block:
                escaped_code = html.escape("\n".join(code_block_lines))
                output_lines.append(f"<pre><code>{escaped_code}</code></pre>")
                code_block_lines = []
                in_code_block = False
            else:
                _flush_paragraph()
                _flush_list()
                _flush_table()
                in_code_block = True
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Multi-line display math blocks ($$ ... $$ or \[ ... \])
        if math_block_delim is not None:
            closing_delim = "$$" if math_block_delim == "$$" else r"\]"
            if stripped == closing_delim:
                escaped_math = html.escape("\n".join(math_block_lines))
                open_d = "$$" if math_block_delim == "$$" else r"\["
                close_d = "$$" if math_block_delim == "$$" else r"\]"
                output_lines.append(f'<div class="math-display">{open_d}\n{escaped_math}\n{close_d}</div>')
                math_block_lines = []
                math_block_delim = None
            else:
                math_block_lines.append(line)
            continue

        if stripped in ("$$", r"\["):
            _flush_paragraph()
            _flush_list()
            _flush_table()
            math_block_delim = stripped
            continue

        # Single-line display math block ($$...$$ or \[...\])
        if (stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4) or (
            stripped.startswith(r"\[") and stripped.endswith(r"\]") and len(stripped) > 4
        ):
            _flush_paragraph()
            _flush_list()
            _flush_table()
            output_lines.append(f'<div class="math-display">{html.escape(stripped)}</div>')
            continue

        is_ul = stripped.startswith("- ") or stripped.startswith("* ")
        ol_match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        is_table_line = stripped.startswith("|") and stripped.endswith("|")

        # End lists if empty line or non-list line
        if in_list and not (is_ul or ol_match):
            _flush_list()

        # End tables if non-table line
        if in_table and not is_table_line:
            _flush_table()

        # Blank line
        if not stripped:
            _flush_paragraph()
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            _flush_paragraph()
            level = len(heading_match.group(1))
            heading_content = _inline_markdown_to_html(heading_match.group(2))
            output_lines.append(f"<h{level}>{heading_content}</h{level}>")
            continue

        # Horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            _flush_paragraph()
            output_lines.append("<hr>")
            continue

        # Blockquote
        if stripped.startswith(">"):
            _flush_paragraph()
            quote_text = _inline_markdown_to_html(stripped.lstrip(">").strip())
            output_lines.append(f"<blockquote><p>{quote_text}</p></blockquote>")
            continue

        # Unordered list (with task list checkbox support)
        if is_ul:
            _flush_paragraph()
            if in_list and list_type != "ul":
                _flush_list()
            if not in_list:
                output_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            raw_item = stripped[2:]
            task_match = re.match(r"^\[([ xX])\]\s+(.*)$", raw_item)
            if task_match:
                checked = " checked" if task_match.group(1).lower() == "x" else ""
                item_html = f'<input type="checkbox"{checked} disabled> {_inline_markdown_to_html(task_match.group(2))}'
            else:
                item_html = _inline_markdown_to_html(raw_item)
            output_lines.append(f"<li>{item_html}</li>")
            continue

        # Ordered list
        if ol_match:
            _flush_paragraph()
            if in_list and list_type != "ol":
                _flush_list()
            if not in_list:
                start_num = int(ol_match.group(1))
                ol_tag = f'<ol start="{start_num}">' if start_num != 1 else "<ol>"
                output_lines.append(ol_tag)
                in_list = True
                list_type = "ol"
            item_text = _inline_markdown_to_html(ol_match.group(2))
            output_lines.append(f"<li>{item_text}</li>")
            continue

        # Tables
        if is_table_line:
            _flush_paragraph()
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            # Skip separator line |---|---|
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            if not in_table:
                output_lines.append("<table><thead><tr>")
                for cell in cells:
                    output_lines.append(f"<th>{_inline_markdown_to_html(cell)}</th>")
                output_lines.append("</tr></thead><tbody>")
                in_table = True
            else:
                output_lines.append("<tr>")
                for cell in cells:
                    output_lines.append(f"<td>{_inline_markdown_to_html(cell)}</td>")
                output_lines.append("</tr>")
            continue

        # Paragraph continuation
        paragraph_lines.append(stripped)

    _flush_paragraph()

    if in_code_block:
        escaped_code = html.escape("\n".join(code_block_lines))
        output_lines.append(f"<pre><code>{escaped_code}</code></pre>")

    if math_block_delim is not None:
        escaped_math = html.escape("\n".join(math_block_lines))
        open_d = "$$" if math_block_delim == "$$" else r"\["
        close_d = "$$" if math_block_delim == "$$" else r"\]"
        output_lines.append(f'<div class="math-display">{open_d}\n{escaped_math}\n{close_d}</div>')

    _flush_list()
    _flush_table()

    return "\n".join(output_lines)


def convert_markdown_to_html(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    with open(src, "r", encoding="utf-8") as f:
        content = f.read()
    body_html = parse_markdown_to_html(content)
    head_extra = KATEX_HEAD_SNIPPET if contains_math(content) else ""
    src_dir = os.path.dirname(os.path.abspath(src)) or "."
    base_uri = html.escape(Path(src_dir).as_uri() + "/", quote=True)
    base_tag = f'<base href="{base_uri}">\n'
    full_html = HTML_TEMPLATE.format(base_tag=base_tag, head_extra=head_extra, content=body_html)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(full_html)
