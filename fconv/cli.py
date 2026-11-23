"""Command-line interface for the universal file converter."""

import argparse
import os
import sys
from typing import Dict, List, Optional

from fconv import __version__
from fconv.engine.doctor import run_doctor, run_install_deps
from fconv.engine.pipeline import Pipeline, PipelineExecutionError, execute_with_fallback
from fconv.graph.node import detect_format_from_path, normalize_format, SUPPORTED_FORMATS
from fconv.graph.registry import get_default_edges
from fconv.graph.router import Router
from fconv.options import ConvertOptions


def _positive_int(flag_name: str):
    def _parse(value: str) -> int:
        try:
            num = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{flag_name} must be an integer, got '{value}'") from exc
        if num <= 0:
            raise argparse.ArgumentTypeError(f"{flag_name} must be greater than 0, got {num}")
        return num

    return _parse


def _quality_int(value: str) -> int:
    try:
        num = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"quality must be an integer, got '{value}'") from exc
    if num < 1 or num > 100:
        raise argparse.ArgumentTypeError(f"quality must be between 1 and 100, got {num}")
    return num


def build_parser(prog_name: Optional[str] = None) -> argparse.ArgumentParser:
    prog = prog_name or os.path.basename(sys.argv[0]) or "convert"
    parser = argparse.ArgumentParser(
        prog=prog,
        allow_abbrev=False,
        description="Universal graph-based file conversion utility across vector, raster, and text formats.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  {prog} diagram.svg figure.pdf
  {prog} document.pdf page.svg --page 1
  {prog} diagram.svg preview.png -dpi=300
  {prog} document.pdf render.png --dpi 600 --page 2
  {prog} notes.md notes.pdf
  {prog} notes.md document.docx
  {prog} photo.png photo.jpg --quality 85
  {prog} --explain notes.md preview.png
  {prog} doctor
  {prog} install-deps
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
        type=_positive_int("dpi"),
        default=None,
        help="Output resolution in dots per inch (e.g. 300, 600).",
    )
    parser.add_argument(
        "-quality", "--quality",
        dest="quality",
        type=_quality_int,
        default=None,
        help="Output quality percentage for lossy formats (1-100).",
    )
    parser.add_argument(
        "-p", "-page", "--page",
        dest="page",
        type=_positive_int("page"),
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
        type=_positive_int("timeout"),
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
    avail_cache: Dict[object, bool] = {}
    for edge in edges:
        fn = edge.check_available
        if fn not in avail_cache:
            avail_cache[fn] = bool(fn())
        avail_str = "Yes" if avail_cache[fn] else "No"
        print(
            f"{edge.source:<8} {edge.target:<8} {edge.engine_name:<15} "
            f"{edge.fidelity.value:<22} {edge.cost:<6} {avail_str:<7} {edge.description}"
        )


def _is_positional_subcommand(args: argparse.Namespace, name: str) -> bool:
    return (
        args.src == name
        and args.dst is None
        and args.from_fmt is None
        and args.to_fmt is None
    )


def main(argv: Optional[List[str]] = None) -> int:
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        prog_name = parser.prog

        # Handle diagnostic flags or standalone positional subcommands
        if args.doctor or _is_positional_subcommand(args, "doctor"):
            run_doctor()
            return 0

        if args.install_deps or _is_positional_subcommand(args, "install-deps"):
            run_install_deps()
            return 0

        edges = get_default_edges()

        if args.list_tools or _is_positional_subcommand(args, "list-tools"):
            list_tools(edges)
            return 0

        # Ensure source and destination files are provided
        if not args.src or not args.dst:
            parser.print_help(sys.stderr)
            return 1

        src_path = args.src
        dst_path = args.dst

        # Determine source format
        if args.from_fmt is not None:
            src_fmt = normalize_format(args.from_fmt)
            if not src_fmt:
                print(
                    f"Error: Unsupported source format '{args.from_fmt}' "
                    f"(Supported: {', '.join(sorted(SUPPORTED_FORMATS))}).",
                    file=sys.stderr,
                )
                return 1
        else:
            src_fmt = detect_format_from_path(src_path)
            if not src_fmt:
                print(
                    f"Error: Unable to detect format from source path '{src_path}'. "
                    f"Use --from to specify explicitly (Supported: {', '.join(sorted(SUPPORTED_FORMATS))}).",
                    file=sys.stderr,
                )
                return 1

        # Determine target format
        if args.to_fmt is not None:
            dst_fmt = normalize_format(args.to_fmt)
            if not dst_fmt:
                print(
                    f"Error: Unsupported target format '{args.to_fmt}' "
                    f"(Supported: {', '.join(sorted(SUPPORTED_FORMATS))}).",
                    file=sys.stderr,
                )
                return 1
        else:
            dst_fmt = detect_format_from_path(dst_path)
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

        if src_fmt == dst_fmt and (
            opts.dpi is not None
            or opts.quality is not None
            or opts.page is not None
            or opts.engine is not None
        ):
            if not opts.quiet and not opts.json_output:
                print(
                    f"[NOTICE] Source and target format are both '{src_fmt}'; "
                    "copying directly and ignoring conversion options.",
                    file=sys.stderr,
                )

        router = Router(edges)

        if opts.explain:
            route = router.find_route(
                source=src_fmt,
                target=dst_fmt,
                forced_engine=opts.engine,
                require_available=True,
            )
            if not route:
                route = router.find_route(
                    source=src_fmt,
                    target=dst_fmt,
                    forced_engine=opts.engine,
                    require_available=False,
                )
                if route:
                    print(
                        "[WARNING] Required tool(s) for this route are missing on this system; "
                        "showing theoretical route.",
                        file=sys.stderr,
                    )
            if route:
                Pipeline(route, opts).explain(src_path, dst_path)
                return 0
        else:
            try:
                record = execute_with_fallback(router, src_fmt, dst_fmt, src_path, dst_path, opts)
            except PipelineExecutionError as exc:
                print(f"\n[CONVERSION FAILED] {exc}", file=sys.stderr)
                return 3
            except FileNotFoundError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            except Exception as exc:
                print(f"Unexpected error: {exc}", file=sys.stderr)
                return 4

            if record:
                if opts.json_output:
                    print(record.to_json())
                elif not opts.quiet:
                    print(record.render_console_summary())
                return 0

        # No route found
        if opts.engine:
            known_engines = {e.engine_name.lower() for e in edges}
            if opts.engine.lower() not in known_engines:
                print(
                    f"Error: Unknown engine '{opts.engine}' for first-hop conversion from '{src_fmt}' to '{dst_fmt}'.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Error: No available route from '{src_fmt}' to '{dst_fmt}' starting with engine '{opts.engine}' "
                    "(note: --engine constrains step 1 only, or the binary may be missing).",
                    file=sys.stderr,
                )
        else:
            print(
                f"Error: No conversion route found from '{src_fmt}' to '{dst_fmt}'.",
                file=sys.stderr,
            )
        print(f"Run '{prog_name} doctor' to inspect missing tools on your system.", file=sys.stderr)
        return 2

    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
