"""Multi-step conversion execution pipeline and temporary workspace manager."""

import os
import shlex
import shutil
import sys
import tempfile
import time
from typing import List, Optional, Set
from fconv.converters.base import ensure_parent_dir
from fconv.engine.telemetry import TelemetryRecord
from fconv.graph.edge import Edge, FidelityClass
from fconv.graph.node import detect_format_from_path
from fconv.graph.router import Route, Router
from fconv.options import ConvertOptions


class PipelineExecutionError(RuntimeError):
    def __init__(self, message: str, failed_edge: Optional[Edge] = None):
        super().__init__(message)
        self.failed_edge = failed_edge


class Pipeline:
    def __init__(self, route: Route, options: ConvertOptions):
        self.route = route
        self.options = options

    def _step_options(self, idx: int, edge: Edge) -> ConvertOptions:
        """Return effective ConvertOptions for a specific pipeline step."""
        if idx == self.route.steps:
            return self.options
        return self.options.for_intermediate(
            preserve_dpi_none=(edge.fidelity == FidelityClass.LOSSLESS_VECTOR)
        )

    def get_notices(self) -> List[str]:
        """Aggregate all non-lossless notices across edges in this route."""
        notices: List[str] = []
        for idx, edge in enumerate(self.route.edges, 1):
            notice = edge.get_notice(self._step_options(idx, edge))
            if notice and notice not in notices:
                notices.append(notice)
        return notices

    def explain(self, src: str, dst: str) -> None:
        """Display the complete conversion route, fidelity notices, and command previews."""
        print(f"\nPlanned Route: {self.route.format_summary()}")
        print(f"Total Steps:   {self.route.steps}")

        notices = self.get_notices()
        if notices:
            print("-" * 60)
            for notice in notices:
                print(f"[NOTICE] {notice}")

        print("-" * 60)

        current_src = src
        for idx, edge in enumerate(self.route.edges, 1):
            is_last = (idx == self.route.steps)
            step_dst = dst if is_last else f"<temp_dir>/step_{idx}.{edge.target}"
            step_opts = self._step_options(idx, edge)

            try:
                cmd = edge.command_preview(current_src, step_dst, step_opts)
                cmd_repr = shlex.join(cmd)
            except Exception as exc:
                cmd_repr = f"[Command preview error: {exc}]"

            fallback_flag = " (fallback)" if edge.is_fallback else ""
            avail_flag = "" if edge.check_available() else " [UNAVAILABLE]"
            step_notice = edge.get_notice(step_opts)
            print(f"Step {idx}: {edge.source.upper()} -> {edge.target.upper()}")
            print(f"  Engine:      {edge.engine_name}{fallback_flag}{avail_flag}")
            print(f"  Fidelity:    {edge.fidelity.value}")
            print(f"  Cost:        {edge.cost}")
            print(f"  Description: {edge.description}")
            if step_notice:
                print(f"  Warning:     {step_notice}")
            print(f"  Command:     {cmd_repr}")
            print("-" * 60)
            current_src = step_dst

    def execute(self, src: str, dst: str) -> Optional[TelemetryRecord]:
        """Execute the conversion route and return a TelemetryRecord."""
        if self.options.explain:
            self.explain(src, dst)
            return None

        if not os.path.exists(src):
            raise FileNotFoundError(f"Source file does not exist: {src}")
        if not os.path.isfile(src):
            raise PipelineExecutionError(f"Source path is not a regular file: {src}")
        if os.path.isdir(dst):
            raise PipelineExecutionError(f"Destination path is a directory: {dst}")

        source_bytes = os.path.getsize(src)
        notices = self.get_notices()

        # Emit pre-flight notices unless suppressed
        if not self.options.quiet and not self.options.json_output:
            for notice in notices:
                print(f"[NOTICE] {notice}", file=sys.stderr)

        start_time = time.perf_counter()

        if self.route.steps == 0:
            same_file = os.path.exists(dst) and os.path.samefile(src, dst)
            if not same_file:
                ensure_parent_dir(dst)
                shutil.copy2(src, dst)
            end_time = time.perf_counter()
            target_bytes = os.path.getsize(dst)
            return TelemetryRecord(
                source_path=src,
                target_path=dst,
                source_bytes=source_bytes,
                target_bytes=target_bytes,
                duration_ms=(end_time - start_time) * 1000.0,
                engines=["copy"],
                fidelities=[FidelityClass.LOSSLESS_CONTAINER.value],
                notices=[],
                options_summary=[],
            )

        if self.options.verbose:
            if self.route.steps == 1:
                edge = self.route.edges[0]
                print(f"[CONVERT] Single-step: {edge.source} -> {edge.target} via {edge.engine_name}", file=sys.stderr)
            else:
                print(f"[CONVERT] Multi-step route: {self.route.format_summary()}", file=sys.stderr)

        with tempfile.TemporaryDirectory(prefix="fconv_pipe_") as temp_dir:
            current_input = src
            for idx, edge in enumerate(self.route.edges, 1):
                is_last = (idx == self.route.steps)
                if is_last:
                    dst_base = os.path.basename(dst)
                    if dst_base and detect_format_from_path(dst_base) == edge.target:
                        staged_name = dst_base
                    else:
                        staged_name = f"output.{edge.target}"
                    current_output = os.path.join(temp_dir, staged_name)
                else:
                    current_output = os.path.join(temp_dir, f"step_{idx}.{edge.target}")

                step_opts = self._step_options(idx, edge)

                if self.options.verbose and self.route.steps > 1:
                    print(
                        f"  -> Step {idx}/{self.route.steps}: {edge.source} -> {edge.target} "
                        f"via {edge.engine_name} [Cost {edge.cost}]",
                        file=sys.stderr,
                    )

                try:
                    edge.execute(current_input, current_output, step_opts)
                except Exception as exc:
                    raise PipelineExecutionError(
                        f"Failed during step {idx} ({edge.source} -> {edge.target} via {edge.engine_name}): {exc}",
                        failed_edge=edge,
                    ) from exc

                if not os.path.isfile(current_output):
                    raise PipelineExecutionError(
                        f"Step {idx} completed but output file was not created: {current_output}",
                        failed_edge=edge,
                    )

                current_input = current_output

            ensure_parent_dir(dst)
            shutil.move(current_input, dst)

        end_time = time.perf_counter()
        target_bytes = os.path.getsize(dst)

        # Collect options summary
        opts_summary: List[str] = []
        if self.options.dpi is not None:
            opts_summary.append(f"{self.options.dpi} DPI")
        if self.options.quality is not None:
            opts_summary.append(f"Quality {self.options.quality}")
        if self.options.page is not None:
            opts_summary.append(f"Page {self.options.page}")

        return TelemetryRecord(
            source_path=src,
            target_path=dst,
            source_bytes=source_bytes,
            target_bytes=target_bytes,
            duration_ms=(end_time - start_time) * 1000.0,
            engines=[e.engine_name for e in self.route.edges],
            fidelities=[e.fidelity.value for e in self.route.edges],
            notices=notices,
            options_summary=opts_summary,
        )


def execute_with_fallback(
    router: Router,
    source_fmt: str,
    target_fmt: str,
    src_path: str,
    dst_path: str,
    opts: ConvertOptions,
    max_attempts: int = 3,
) -> Optional[TelemetryRecord]:
    """Execute a conversion and retry alternative routes if an unforced engine fails."""
    excluded_edges: Set[str] = set()
    route = router.find_route(
        source=source_fmt,
        target=target_fmt,
        forced_engine=opts.engine,
        require_available=True,
        excluded_edges=excluded_edges,
    )
    if not route:
        return None

    attempts = 0
    while True:
        attempts += 1
        pipeline = Pipeline(route, opts)
        try:
            return pipeline.execute(src_path, dst_path)
        except PipelineExecutionError as exc:
            if opts.engine or not exc.failed_edge or attempts >= max_attempts:
                raise
            excluded_edges.add(exc.failed_edge.key)
            next_route = router.find_route(
                source=source_fmt,
                target=target_fmt,
                forced_engine=None,
                require_available=True,
                excluded_edges=excluded_edges,
            )
            if not next_route:
                raise
            if not opts.quiet:
                print(
                    f"[FALLBACK] Step failed via {exc.failed_edge.engine_name}; "
                    f"retrying via {next_route.format_summary()}",
                    file=sys.stderr,
                )
            route = next_route
