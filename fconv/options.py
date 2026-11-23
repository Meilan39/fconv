"""Conversion options passed across CLI, graph router, and adapter engines."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConvertOptions:
    dpi: Optional[int] = None
    quality: Optional[int] = None
    page: Optional[int] = None
    engine: Optional[str] = None
    verbose: bool = False
    explain: bool = False
    quiet: bool = False
    json_output: bool = False
    timeout: int = 60

    def for_intermediate(self, preserve_dpi_none: bool = False) -> "ConvertOptions":
        """Return options tailored for intermediate transformation steps."""
        dpi = self.dpi if preserve_dpi_none else (self.dpi if self.dpi is not None else 300)
        quality = max(self.quality, 95) if self.quality is not None else 95
        return ConvertOptions(
            dpi=dpi,
            quality=quality,
            page=self.page,
            engine=None,
            verbose=self.verbose,
            explain=self.explain,
            quiet=self.quiet,
            json_output=self.json_output,
            timeout=self.timeout,
        )
