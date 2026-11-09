"""Graph edge model representing an atomic format transformation."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional
from fconv.options import ConvertOptions


class FidelityClass(str, Enum):
    LOSSLESS_VECTOR = "lossless_vector"
    LOSSLESS_RASTER = "lossless_raster"
    LOSSLESS_CONTAINER = "lossless_container"
    VECTOR_RASTERIZATION = "vector_rasterization"
    LOSSY_COMPRESSION = "lossy_compression"
    SEMANTIC_DEGRADATION = "semantic_degradation"
    PROBABILISTIC_OCR = "probabilistic_ocr"

    @property
    def is_lossless(self) -> bool:
        return self in (
            FidelityClass.LOSSLESS_VECTOR,
            FidelityClass.LOSSLESS_RASTER,
            FidelityClass.LOSSLESS_CONTAINER,
        )


@dataclass
class Edge:
    source: str
    target: str
    engine_name: str
    cost: int
    is_fallback: bool
    description: str
    check_available: Callable[[], bool]
    execute: Callable[[str, str, ConvertOptions], None]
    command_preview: Callable[[str, str, ConvertOptions], List[str]]
    fidelity: FidelityClass = FidelityClass.LOSSLESS_RASTER

    @property
    def key(self) -> str:
        return f"{self.source}->{self.target}:{self.engine_name}"

    def get_notice(self, opts: ConvertOptions) -> Optional[str]:
        """Generate human-readable warning notice if conversion is lossy or degrading."""
        if self.fidelity == FidelityClass.VECTOR_RASTERIZATION:
            dpi_str = f" at {opts.dpi or 300} DPI" if (opts.dpi or self.source in ("svg", "pdf")) else ""
            return f"Irreversible vector rasterization ({self.source.upper()} -> {self.target.upper()}{dpi_str})"

        if self.fidelity == FidelityClass.LOSSY_COMPRESSION:
            quality_info = f" (Quality: {opts.quality})" if opts.quality is not None else ""
            return f"Lossy image compression applied ({self.source.upper()} -> {self.target.upper()}{quality_info})"

        if self.fidelity == FidelityClass.SEMANTIC_DEGRADATION:
            return f"Document layout and visual styling flattened ({self.source.upper()} -> {self.target.upper()})"

        if self.fidelity == FidelityClass.PROBABILISTIC_OCR:
            return f"Heuristic text extraction via OCR ({self.source.upper()} -> {self.target.upper()}); accuracy depends on image clarity"

        return None

    def __repr__(self) -> str:
        fallback_flag = " (fallback)" if self.is_fallback else ""
        return (
            f"Edge({self.source} -> {self.target} via {self.engine_name}, "
            f"cost={self.cost}, fidelity={self.fidelity.value}{fallback_flag})"
        )
