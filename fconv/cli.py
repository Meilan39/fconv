"""Command-line interface for the universal file converter."""

import argparse
import sys
from typing import List, Optional

from fconv import __version__
from fconv.engine.doctor import run_doctor, run_install_deps
from fconv.engine.pipeline import Pipeline, PipelineExecutionError
from fconv.graph.node import detect_format_from_path, normalize_format, SUPPORTED_FORMATS
from fconv.graph.registry import get_default_edges
from fconv.graph.router import Router
from fconv.options import ConvertOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="convert",
        description="Universal graph-based file conversion utility across vector, raster, and text formats.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  convert diagram.svg figure.pdf
  convert document.pdf page.svg --page 1
  convert diagram.svg preview.png -dpi=300
  convert document.pdf render.png --dpi 600 --page 2
  convert notes.md notes.pdf
  convert notes.md document.docx
  convert photo.png photo.jpg --quality 85
  convert --explain notes.md preview.png
  convert doctor
  convert install-deps
        """,
    )

    # Subcommands / Positional files
    parser.add_argument(
        "src",
        nargs="?",
        help="Path to the source file to convert, or subcommand (doctor, install-deps, list-tools).",
    )
    parser.add_argument(
        "dst",
        nargs="?",
        help="Path to the target destination file.",
    )

    # Conversion options
    parser.add_argument(
        "-d", "-dpi", "--dpi",
        dest="dpi",
        type=int,
        default=None,
        help="Output resolution in dots per inch (e.g. 300, 600).",
    )
    parser.add_argument(
        "-quality", "--quality",
        dest="quality",
        type=int,
        default=None,
        help="Output quality percentage for lossy formats (1-100).",
    )
    parser.add_argument(
        "-p", "-page", "--page",
        dest="page",
        type=int,
        default=None,
        help="Specific page number to extract from multi-page documents (1-indexed).",
    )
    parser.add_argument(
        "-e", "--engine",
        dest="engine",
        type=str,
        default=None,
        help="Force a specific conversion engine for the first transformation step.",
    )
    parser.add_argument(
        "--from",
        dest="from_fmt",
        type=str,
        default=None,
        help="Explicitly override source format (e.g. svg, pdf, md).",
    )
    parser.add_argument(
        "--to",
        dest="to_fmt",
        type=str,
        default=None,
        help="Explicitly override target format (e.g. png, html, docx).",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Display the chosen graph route, warnings, and command line steps without executing.",
    )
    parser.add_argument(
        "-s", "--silent", "--quiet",
        dest="quiet",
        action="store_true",
        help="Suppress all standard completion and warning messages.",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output structured telemetry record as JSON.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable detailed execution logging.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds for external conversion commands (default: 60).",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Inspect system tool installations and print health report.",
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Display Homebrew installation instructions for recommended dependencies.",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List all registered transformation tools, fidelity levels, and availability.",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def list_tools(edges) -> None:
    print("\n=== Registered Conversion Edges ===")
    print(f"{'Source':<8} {'Target':<8} {'Engine':<15} {'Fidelity':<22} {'Cost':<6} {'Avail':<7} {'Description'}")
    print("-" * 95)
    for edge in edges:
        avail_str = "Yes" if edge.check_available() else "No"
        print(
            f"{edge.source:<8} {edge.target:<8} {edge.engine_name:<15} "
            f"{edge.fidelity.value:<22} {edge.cost:<6} {avail_str:<7} {edge.description}"
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Handle special subcommand keywords in position 1
    if args.src == "doctor" or args.doctor:
        run_doctor()
        return 0

    if args.src == "install-deps" or args.install_deps:
        run_install_deps()
        return 0

    edges = get_default_edges()

    if args.src == "list-tools" or args.list_tools:
        list_tools(edges)
        return 0

    # Ensure source and destination files are provided
    if not args.src or not args.dst:
        parser.print_help()
        return 1

    src_path = args.src
    dst_path = args.dst

    # Determine source format
    src_fmt = normalize_format(args.from_fmt) if args.from_fmt else detect_format_from_path(src_path)
    if not src_fmt:
        print(
            f"Error: Unable to detect format from source path '{src_path}'. "
            f"Use --from to specify explicitly (Supported: {', '.join(sorted(SUPPORTED_FORMATS))}).",
            file=sys.stderr,
        )
        return 1

    # Determine target format
    dst_fmt = normalize_format(args.to_fmt) if args.to_fmt else detect_format_from_path(dst_path)
    if not dst_fmt:
        print(
            f"Error: Unable to detect format from destination path '{dst_path}'. "
            f"Use --to to specify explicitly (Supported: {', '.join(sorted(SUPPORTED_FORMATS))}).",
            file=sys.stderr,
        )
        return 1

    # Build options
    opts = ConvertOptions(
        dpi=args.dpi,
        quality=args.quality,
        page=args.page,
        engine=args.engine,
        verbose=args.verbose,
        explain=args.explain,
        quiet=args.quiet,
        json_output=args.json_output,
        timeout=args.timeout,
    )

    # Route search
    router = Router(edges)
    route = router.find_route(
        source=src_fmt,
        target=dst_fmt,
        forced_engine=opts.engine,
        require_available=not opts.explain,
    )

    if not route:
        print(
            f"Error: No conversion route found from '{src_fmt}' to '{dst_fmt}'.",
            file=sys.stderr,
        )
        print("Run 'convert doctor' to inspect missing tools on your system.", file=sys.stderr)
        return 2

    # Execute conversion pipeline
    pipeline = Pipeline(route, opts)
    try:
        record = pipeline.execute(src_path, dst_path)
        if record:
            if opts.json_output:
                print(record.to_json())
            elif not opts.quiet:
                print(record.render_console_summary())
        return 0
    except PipelineExecutionError as exc:
        print(f"\n[CONVERSION FAILED] {exc}", file=sys.stderr)
        return 3
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
