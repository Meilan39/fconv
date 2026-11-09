"""Telemetry collection, size metrics, and clean logging formatters."""

import json
import os
from dataclasses import asdict, dataclass
from typing import List, Optional


def format_bytes(num_bytes: int) -> str:
    """Format byte counts into human-readable strings."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_ratio(src_bytes: int, dst_bytes: int) -> str:
    """Calculate percentage change between source and destination sizes."""
    if src_bytes <= 0:
        return "+0.0%"
    delta = dst_bytes - src_bytes
    pct = (delta / src_bytes) * 100.0
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


@dataclass
class TelemetryRecord:
    source_path: str
    target_path: str
    source_bytes: int
    target_bytes: int
    duration_ms: float
    engines: List[str]
    fidelities: List[str]
    notices: List[str]
    options_summary: List[str]

    @property
    def ratio_str(self) -> str:
        return format_ratio(self.source_bytes, self.target_bytes)

    @property
    def source_size_str(self) -> str:
        return format_bytes(self.source_bytes)

    @property
    def target_size_str(self) -> str:
        return format_bytes(self.target_bytes)

    def render_console_summary(self) -> str:
        """Render minimal, clean single-line completion log."""
        src_base = os.path.basename(self.source_path)
        dst_base = os.path.basename(self.target_path)
        engines_str = ", ".join(self.engines)

        parts = [
            f"[SUCCESS] {src_base} ({self.source_size_str}) -> {dst_base} ({self.target_size_str}, {self.ratio_str})"
        ]

        if self.options_summary:
            parts.append(" | ".join(self.options_summary))

        duration_str = f"{self.duration_ms:.1f}ms" if self.duration_ms < 1000 else f"{self.duration_ms / 1000:.2f}s"
        parts.append(f"{duration_str} via {engines_str}")

        return " | ".join(parts)

    def to_json(self) -> str:
        """Render JSON telemetry record for automated pipelines."""
        payload = {
            "source": self.source_path,
            "target": self.target_path,
            "source_bytes": self.source_bytes,
            "target_bytes": self.target_bytes,
            "ratio": round(self.target_bytes / self.source_bytes, 4) if self.source_bytes > 0 else 1.0,
            "duration_ms": round(self.duration_ms, 2),
            "engines": self.engines,
            "fidelities": self.fidelities,
            "notices": self.notices,
            "options": self.options_summary,
        }
        return json.dumps(payload, indent=2)
