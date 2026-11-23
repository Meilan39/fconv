"""Subprocess execution wrapper with error formatting and timeout handling."""

import os
import shlex
import shutil
import signal
import subprocess
import sys
from typing import List, Optional, Union

_EXTRA_PATH_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/Library/TeX/texbin",
)


def _build_search_path(base_path: Optional[str] = None) -> str:
    """Build a PATH string including common macOS/Homebrew/TeX binary directories."""
    raw = os.environ.get("PATH", "") if base_path is None else base_path
    parts = [p for p in raw.split(os.pathsep) if p]
    for extra_dir in _EXTRA_PATH_DIRS:
        if extra_dir not in parts and os.path.isdir(extra_dir):
            parts.append(extra_dir)
    return os.pathsep.join(parts)


def _decode_output(data: Optional[Union[str, bytes]]) -> str:
    """Safely decode subprocess byte output using UTF-8 replacement."""
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


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
        cmd_str = shlex.join(cmd)
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
    """Find absolute path for a system binary using augmented search PATH."""
    return shutil.which(binary_name, path=_build_search_path())


def run_process(
    cmd: List[str],
    timeout: int = 60,
    verbose: bool = False,
    cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Run an external tool command and return CompletedProcess."""
    if verbose:
        print(f"  [EXEC] {shlex.join(cmd)}", file=sys.stderr)

    env = os.environ.copy()
    env["PATH"] = _build_search_path(env.get("PATH"))

    popen_kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": env,
        "cwd": cwd,
    }
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
    except FileNotFoundError as exc:
        raise ProcessExecutionError(
            cmd=cmd,
            exit_code=127,
            stdout="",
            stderr=f"Binary not found: {cmd[0]}",
        ) from exc
    except PermissionError as exc:
        if os.path.sep not in cmd[0] and resolve_binary(cmd[0]) is None:
            raise ProcessExecutionError(
                cmd=cmd,
                exit_code=127,
                stdout="",
                stderr=f"Binary not found: {cmd[0]}",
            ) from exc
        raise ProcessExecutionError(
            cmd=cmd,
            exit_code=126,
            stdout="",
            stderr=f"Permission denied: {cmd[0]}",
        ) from exc
    except OSError as exc:
        raise ProcessExecutionError(
            cmd=cmd,
            exit_code=1,
            stdout="",
            stderr=str(exc),
        ) from exc

    try:
        raw_stdout, raw_stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            proc.kill()
        proc.wait()
        out_str = _decode_output(exc.stdout)
        err_str = _decode_output(exc.stderr).strip()
        timeout_msg = f"Command timed out after {timeout} seconds"
        if err_str:
            timeout_msg = f"{timeout_msg}\n{err_str}"
        raise ProcessExecutionError(
            cmd=cmd,
            exit_code=124,
            stdout=out_str,
            stderr=timeout_msg,
        ) from exc

    stdout = _decode_output(raw_stdout)
    stderr = _decode_output(raw_stderr)

    if proc.returncode != 0:
        raise ProcessExecutionError(
            cmd=cmd,
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
    )
