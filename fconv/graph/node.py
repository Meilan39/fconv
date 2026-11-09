"""Format normalization and extension resolution."""

import os
from typing import Dict, Optional, Set

# Mapping of file extensions to canonical format identifiers
EXTENSION_MAP: Dict[str, str] = {
    # Vector formats
    "svg": "svg",
    "svgz": "svg",
    "pdf": "pdf",
    
    # Raster formats
    "png": "png",
    "jpg": "jpg",
    "jpeg": "jpg",
    "jpe": "jpg",
    "jfif": "jpg",
    "webp": "webp",
    "tiff": "tiff",
    "tif": "tiff",
    "bmp": "bmp",
    "gif": "gif",
    
    # Document and text formats
    "md": "md",
    "markdown": "md",
    "mdown": "md",
    "mkd": "md",
    "html": "html",
    "htm": "html",
    "xhtml": "html",
    "txt": "txt",
    "text": "txt",
    "rtf": "rtf",
    "docx": "docx",
}

# Supported canonical formats
SUPPORTED_FORMATS: Set[str] = set(EXTENSION_MAP.values())


def normalize_format(ext_or_name: str) -> Optional[str]:
    """Normalize file extension or format name into a canonical format string."""
    cleaned = ext_or_name.strip().lower()
    if cleaned.startswith("."):
        cleaned = cleaned[1:]
    return EXTENSION_MAP.get(cleaned)


def detect_format_from_path(file_path: str) -> Optional[str]:
    """Extract and normalize canonical format from a file path."""
    _, ext = os.path.splitext(file_path)
    if not ext:
        return None
    return normalize_format(ext)
