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

    def for_intermediate(self) -> "ConvertOptions":
        """Return options tailored for intermediate transformation steps."""
        return ConvertOptions(
            dpi=self.dpi or 300,
            quality=self.quality or 95,
            page=self.page,
            engine=None,
            verbose=self.verbose,
            explain=self.explain,
            quiet=self.quiet,
            json_output=self.json_output,
            timeout=self.timeout,
        )
