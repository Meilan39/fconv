"""Subprocess execution wrapper with error formatting and timeout handling."""

import os
import shutil
import subprocess
from typing import List, Optional


class ProcessExecutionError(RuntimeError):
    def __init__(
        self,
        cmd: List[str],
        exit_code: int,
        stdout: str,
        stderr: str,
    ):
        self.cmd = cmd
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        cmd_str = " ".join(cmd)
        message = (
            f"Command failed with exit code {exit_code}:\n"
            f"  Command: {cmd_str}\n"
        )
        if stderr.strip():
            message += f"  Error: {stderr.strip()}\n"
        elif stdout.strip():
            message += f"  Output: {stdout.strip()}\n"
        super().__init__(message)


def resolve_binary(binary_name: str) -> Optional[str]:
    """Find absolute path for a system binary."""
    return shutil.which(binary_name)


def run_process(
    cmd: List[str],
    timeout: int = 60,
    verbose: bool = False,
    cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Run an external tool command and return CompletedProcess."""
    if verbose:
        print(f"  [EXEC] {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProcessExecutionError(
            cmd=cmd,
            exit_code=124,
            stdout=exc.stdout or "",
            stderr=f"Command timed out after {timeout} seconds",
        ) from exc
    except FileNotFoundError as exc:
        raise ProcessExecutionError(
            cmd=cmd,
            exit_code=127,
            stdout="",
            stderr=f"Binary not found: {cmd[0]}",
        ) from exc

    if result.returncode != 0:
        raise ProcessExecutionError(
            cmd=cmd,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    return result
