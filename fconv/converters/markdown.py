"""Zero-dependency Markdown parser and HTML generator."""

import html
import re
from typing import List
from fconv.converters.base import ensure_parent_dir
from fconv.options import ConvertOptions


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Converted Document</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
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
    font-size: 85%;
    padding: 0.2em 0.4em;
    font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
  }}
  pre {{
    background-color: #f6f8fa;
    border-radius: 6px;
    font-size: 85%;
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
  @media print {{
    body {{
      margin: 15mm 20mm;
      max-width: none;
    }}
  }}
</style>
</head>
<body>
{content}
</body>
</html>
"""


def _inline_markdown_to_html(text: str) -> str:
    """Transform inline markdown elements to HTML."""
    # Escape HTML special characters first
    text = html.escape(text)

    # Inline code: `code`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Images: ![alt](url)
    text = re.sub(r"!\[(.*?)\]\((.*?)\)", r'<img src="\2" alt="\1">', text)

    # Links: [text](url)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', text)

    # Bold: **text** or __text__
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.*?)__", r"<strong>\1</strong>", text)

    # Italic: *text* or _text_
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.*?)_", r"<em>\1</em>", text)

    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.*?)~~", r"<del>\1</del>", text)

    return text


def parse_markdown_to_html(md_text: str) -> str:
    """Convert Markdown string to HTML body content."""
    lines = md_text.splitlines()
    output_lines: List[str] = []
    in_code_block = False
    code_block_lines: List[str] = []
    in_list = False
    list_type = "ul"
    in_table = False
    table_header_parsed = False

    for line in lines:
        stripped = line.strip()

        # Fenced code blocks
        if stripped.startswith("```"):
            if in_code_block:
                escaped_code = html.escape("\n".join(code_block_lines))
                output_lines.append(f"<pre><code>{escaped_code}</code></pre>")
                code_block_lines = []
                in_code_block = False
            else:
                if in_list:
                    output_lines.append(f"</{list_type}>")
                    in_list = False
                in_code_block = True
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # End lists if empty line or non-list line
        if in_list and not (stripped.startswith("- ") or stripped.startswith("* ") or re.match(r"^\d+\.\s+", stripped)):
            output_lines.append(f"</{list_type}>")
            in_list = False

        # End tables if non-table line
        if in_table and not (stripped.startswith("|") and stripped.endswith("|")):
            output_lines.append("</tbody></table>")
            in_table = False
            table_header_parsed = False

        # Blank line
        if not stripped:
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            heading_content = _inline_markdown_to_html(heading_match.group(2))
            output_lines.append(f"<h{level}>{heading_content}</h{level}>")
            continue

        # Horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            output_lines.append("<hr>")
            continue

        # Blockquote
        if stripped.startswith(">"):
            quote_text = _inline_markdown_to_html(stripped.lstrip(">").strip())
            output_lines.append(f"<blockquote><p>{quote_text}</p></blockquote>")
            continue

        # Unordered list
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                output_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            item_text = _inline_markdown_to_html(stripped[2:])
            output_lines.append(f"<li>{item_text}</li>")
            continue

        # Ordered list
        ol_match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if ol_match:
            if not in_list:
                output_lines.append("<ol>")
                in_list = True
                list_type = "ol"
            item_text = _inline_markdown_to_html(ol_match.group(2))
            output_lines.append(f"<li>{item_text}</li>")
            continue

        # Tables
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            # Check if this is the separator line |---|---|
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            if not in_table:
                output_lines.append("<table><thead><tr>")
                for cell in cells:
                    output_lines.append(f"<th>{_inline_markdown_to_html(cell)}</th>")
                output_lines.append("</tr></thead><tbody>")
                in_table = True
                table_header_parsed = True
            else:
                output_lines.append("<tr>")
                for cell in cells:
                    output_lines.append(f"<td>{_inline_markdown_to_html(cell)}</td>")
                output_lines.append("</tr>")
            continue

        # Paragraph
        para_content = _inline_markdown_to_html(stripped)
        output_lines.append(f"<p>{para_content}</p>")

    if in_code_block:
        escaped_code = html.escape("\n".join(code_block_lines))
        output_lines.append(f"<pre><code>{escaped_code}</code></pre>")

    if in_list:
        output_lines.append(f"</{list_type}>")

    if in_table:
        output_lines.append("</tbody></table>")

    return "\n".join(output_lines)


def convert_markdown_to_html(src: str, dst: str, opts: ConvertOptions) -> None:
    ensure_parent_dir(dst)
    with open(src, "r", encoding="utf-8") as f:
        content = f.read()
    body_html = parse_markdown_to_html(content)
    full_html = HTML_TEMPLATE.format(content=body_html)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(full_html)
