"""Multi-step conversion execution pipeline and temporary workspace manager."""

import os
import shutil
import tempfile
import time
from typing import List, Optional
from fconv.engine.telemetry import TelemetryRecord
from fconv.graph.router import Route
from fconv.options import ConvertOptions


class PipelineExecutionError(RuntimeError):
    pass


class Pipeline:
    def __init__(self, route: Route, options: ConvertOptions):
        self.route = route
        self.options = options

    def get_notices(self) -> List[str]:
        """Aggregate all non-lossless notices across edges in this route."""
        notices: List[str] = []
        for edge in self.route.edges:
            notice = edge.get_notice(self.options)
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
            step_opts = self.options if is_last else self.options.for_intermediate()

            try:
                cmd = edge.command_preview(current_src, step_dst, step_opts)
                cmd_repr = " ".join(cmd)
            except Exception as exc:
                cmd_repr = f"[Command preview error: {exc}]"

            fallback_flag = " (fallback)" if edge.is_fallback else ""
            step_notice = edge.get_notice(self.options)
            print(f"Step {idx}: {edge.source.upper()} -> {edge.target.upper()}")
            print(f"  Engine:      {edge.engine_name}{fallback_flag}")
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

        source_bytes = os.path.getsize(src)
        notices = self.get_notices()

        # Emit pre-flight notices unless suppressed
        if not self.options.quiet and not self.options.json_output:
            for notice in notices:
                print(f"[NOTICE] {notice}")

        start_time = time.perf_counter()

        if self.route.steps == 0:
            if os.path.abspath(src) != os.path.abspath(dst):
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
                fidelities=["lossless"],
                notices=[],
                options_summary=[],
            )

        # Single-hop execution
        if self.route.steps == 1:
            edge = self.route.edges[0]
            if self.options.verbose:
                print(f"[CONVERT] Single-step: {edge.source} -> {edge.target} via {edge.engine_name}")
            edge.execute(src, dst, self.options)
        else:
            # Multi-hop execution with temporary workspace
            if self.options.verbose:
                print(f"[CONVERT] Multi-step route: {self.route.format_summary()}")

            with tempfile.TemporaryDirectory(prefix="fconv_pipe_") as temp_dir:
                current_input = src
                for idx, edge in enumerate(self.route.edges, 1):
                    is_last = (idx == self.route.steps)
                    current_target_ext = edge.target
                    current_output = dst if is_last else os.path.join(temp_dir, f"step_{idx}.{current_target_ext}")
                    step_opts = self.options if is_last else self.options.for_intermediate()

                    if self.options.verbose:
                        print(
                            f"  -> Step {idx}/{self.route.steps}: {edge.source} -> {edge.target} "
                            f"via {edge.engine_name} [Cost {edge.cost}]"
                        )

                    try:
                        edge.execute(current_input, current_output, step_opts)
                    except Exception as exc:
                        raise PipelineExecutionError(
                            f"Failed during step {idx} ({edge.source} -> {edge.target} via {edge.engine_name}): {exc}"
                        ) from exc

                    if not os.path.exists(current_output):
                        raise PipelineExecutionError(
                            f"Step {idx} completed but output file was not created: {current_output}"
                        )

                    current_input = current_output

        end_time = time.perf_counter()
        target_bytes = os.path.getsize(dst)

        # Collect options summary
        opts_summary: List[str] = []
        if self.options.dpi:
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
