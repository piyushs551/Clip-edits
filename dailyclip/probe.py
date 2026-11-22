"""ffprobe wrapper."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .util import BadFileError, require_ffmpeg

BROWSER_CONTAINERS = {".mp4", ".m4v", ".mov", ".webm"}
BROWSER_VIDEO = {"h264", "vp8", "vp9", "av1"}
BROWSER_AUDIO = {"aac", "mp3", "opus", "vorbis", None}


def build_probe_cmd(path: str) -> list[str]:
    return [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]


def _fps(rate: str | None) -> float:
    try:
        num, den = (rate or "0/1").split("/")
        return round(float(num) / float(den), 3) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def parse_probe(data: dict, path: str) -> dict:
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and s.get("disposition", {}).get("attached_pic") != 1), None)
    if not video:
        raise BadFileError("This file has no video stream, so it can't be edited here.")
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})
    try:
        duration = float(fmt.get("duration") or video.get("duration") or 0)
    except ValueError:
        duration = 0.0
    if duration <= 0:
        raise BadFileError("Couldn't read a duration from this file. It may be damaged.")
    info = {
        "path": str(path),
        "name": Path(path).name,
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": _fps(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "vcodec": video.get("codec_name"),
        "pix_fmt": video.get("pix_fmt"),
        "acodec": audio.get("codec_name") if audio else None,
        "has_audio": audio is not None,
    }
    info["browser_playable"] = is_browser_playable(info)
    return info


def is_browser_playable(info: dict) -> bool:
    """Heuristic: will Chrome/Edge play this natively?"""
    ext = Path(info["path"]).suffix.lower()
    pix = info.get("pix_fmt") or ""
    return (
        ext in BROWSER_CONTAINERS
        and info.get("vcodec") in BROWSER_VIDEO
        and info.get("acodec") in BROWSER_AUDIO
        and ("10" not in pix and "12" not in pix)
    )


def probe(path: str) -> dict:
    require_ffmpeg()
    p = Path(path)
    if not p.is_file():
        raise BadFileError(f"File not found: {path}")
    try:
        res = subprocess.run(build_probe_cmd(str(p)), capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
    except subprocess.TimeoutExpired:
        raise BadFileError("ffprobe timed out reading this file.")
    if res.returncode != 0:
        detail = (res.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        raise BadFileError(f"This doesn't look like a valid video file ({detail[0]}).")
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError:
        raise BadFileError("ffprobe returned unreadable output for this file.")
    return parse_probe(data, str(p))
