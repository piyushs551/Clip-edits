"""Small helpers: errors, ffmpeg discovery, slugs, font lookup."""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BUNDLED_FONT = BASE_DIR / "static" / "fonts" / "Poppins-Bold.ttf"

FFMPEG_INSTALL_HINT = "winget install Gyan.FFmpeg"


class DailyClipError(Exception):
    """Base class for errors that should be shown to the user as-is."""

    code = "error"
    status = 400


class FFmpegMissing(DailyClipError):
    code = "ffmpeg_missing"
    status = 500


class BadFileError(DailyClipError):
    code = "bad_file"


class ValidationError(DailyClipError):
    code = "invalid"


class FFmpegFailed(DailyClipError):
    code = "ffmpeg_failed"
    status = 500


def ffmpeg_status() -> dict:
    """Report whether ffmpeg and ffprobe are on PATH."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    ok = bool(ffmpeg and ffprobe)
    msg = ""
    if not ok:
        missing = " and ".join(n for n, p in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not p)
        msg = (
            f"{missing} not found on PATH. Install it with:  {FFMPEG_INSTALL_HINT}\n"
            "then close and reopen your terminal so PATH updates."
        )
    return {"ok": ok, "ffmpeg": ffmpeg, "ffprobe": ffprobe, "message": msg}


def require_ffmpeg() -> None:
    st = ffmpeg_status()
    if not st["ok"]:
        raise FFmpegMissing(st["message"])


def slugify(text: str, default: str = "short", max_len: int = 50) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:max_len].strip("-") or default


def output_name(slug: str, day: date | None = None) -> str:
    day = day or date.today()
    return f"{day:%Y-%m-%d}_{slugify(slug)}.mp4"


def unique_path(path: Path) -> Path:
    """Return path, or path with -2, -3 ... if it already exists."""
    if not path.exists():
        return path
    i = 2
    while True:
        cand = path.with_name(f"{path.stem}-{i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def clean_user_path(raw: str) -> str:
    """Strip quotes/whitespace (Windows 'Copy as path' adds quotes)."""
    return (raw or "").strip().strip('"').strip("'").strip()


def find_font() -> str:
    """Bundled Poppins Bold first, then common bold system fonts."""
    candidates = [
        BUNDLED_FONT,
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    raise DailyClipError(
        "No bold font found. Put Poppins-Bold.ttf in static/fonts/ (see README)."
    )
