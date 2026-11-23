"""Base utilities for converter implementations."""

import os
from fconv.engine.process import resolve_binary


def is_tool_installed(binary_name: str) -> bool:
    """Return True if the binary executable exists in PATH."""
    return resolve_binary(binary_name) is not None


def ensure_parent_dir(path: str) -> None:
    """Create parent directories for the given path if they do not exist."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
