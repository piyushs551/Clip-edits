"""Run ffmpeg commands (the only place that spawns long processes)."""
from __future__ import annotations

import subprocess
from typing import Callable, Optional

from .util import FFmpegFailed, require_ffmpeg


def run_simple(cmd: list[str], timeout: int = 300) -> None:
    require_ffmpeg()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise FFmpegFailed("ffmpeg took too long and was stopped.")
    if res.returncode != 0:
        raise FFmpegFailed(_tail(res.stderr))


def run_with_progress(cmd: list[str], total_seconds: float,
                      on_progress: Optional[Callable[[float], None]] = None) -> None:
    """Run ffmpeg with `-progress pipe:1`, reporting 0..1."""
    require_ffmpeg()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    log: list[str] = []
    for line in proc.stdout:  # type: ignore[union-attr]
        line = line.strip()
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            try:
                secs = int(line.split("=", 1)[1]) / 1_000_000
            except ValueError:
                continue
            if on_progress and total_seconds > 0:
                on_progress(max(0.0, min(0.99, secs / total_seconds)))
        elif "=" not in line or line.startswith(("Error", "[")):
            if line:
                log.append(line)
    proc.wait()
    if proc.returncode != 0:
        raise FFmpegFailed(_tail("\n".join(log)))
    if on_progress:
        on_progress(1.0)


def _tail(text: str, n: int = 6) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return "ffmpeg failed: " + (" | ".join(lines[-n:]) if lines else "unknown error")
