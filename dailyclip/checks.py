"""Pre-export checklist built from the DailyClip rules (see .claude/skills/).

Pure functions: they take an ExportSpec and return a list of results; nothing is
blocked, the UI just shows what to fix.

Rules: text on frame one / hook in the first 3 s, lines of <= 6 words, text inside
the safe areas, Short under 30 s, something changes every 2-4 s, clean last frame,
privacy check of the source frames.
"""
from __future__ import annotations

from .commands import (H, SAFE_BOTTOM, SAFE_RIGHT, SAFE_TOP, W, ExportSpec, TextOverlay,
                       border_width, line_height)

MAX_SECONDS = 30.0
MAX_WORDS = 6
HOOK_WINDOW = 3.0
FRAME_ONE = 0.2
MAX_CHANGE_GAP = 4.0
LAST_FRAME_TOLERANCE = 0.15

# Poppins Bold advance widths in em (measured), plus a small safety margin
_UPPER, _LOWER, _DIGIT, _SPACE, _OTHER = 0.68, 0.60, 0.60, 0.21, 0.37
_MARGIN = 1.03


def estimate_text_width(text: str, size: int) -> float:
    """Approximate rendered width in px of one line of Poppins Bold (without outline)."""
    em = 0.0
    for ch in text:
        if ch.isupper():
            em += _UPPER
        elif ch.isalpha():
            em += _LOWER
        elif ch.isdigit():
            em += _DIGIT
        elif ch == " ":
            em += _SPACE
        else:
            em += _OTHER
    return em * size * _MARGIN


def is_label(t: TextOverlay) -> bool:
    """A small positioned label (e.g. the red 'DAY 1'), not a hook/caption line."""
    return t.x is not None


def _end(t: TextOverlay, clip_len: float) -> float:
    return clip_len if t.end is None else min(t.end, clip_len)


def _short(text: str, n: int = 28) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _result(id_: str, ok: bool, message: str, status: str | None = None) -> dict:
    return {"id": id_, "status": status or ("pass" if ok else "warn"), "message": message}


def check_length(spec: ExportSpec) -> dict:
    total = spec.total_duration
    if total < MAX_SECONDS:
        return _result("length", True, f"Length {total:.1f} s (under {MAX_SECONDS:.0f} s).")
    return _result("length", False,
                   f"Length {total:.1f} s - keep Shorts under {MAX_SECONDS:.0f} s.")


def check_hook(spec: ExportSpec) -> dict:
    hooks = [t for t in spec.texts if not is_label(t)]
    if not hooks:
        return _result("hook", False, "No hook text: put the payoff or tension on screen in the "
                       "first 3 s (frame one).")
    first = min(t.start for t in hooks)
    if first <= FRAME_ONE:
        return _result("hook", True, "Hook text is on frame one.")
    if first <= HOOK_WINDOW:
        return _result("hook", False, f"Hook text starts at {first:.1f} s - show it on frame one.")
    return _result("hook", False, f"First text appears at {first:.1f} s - the hook must land "
                   f"within the first {HOOK_WINDOW:.0f} s.")


def check_words(spec: ExportSpec) -> dict:
    bad = []
    for t in spec.texts:
        for line in t.lines():
            n = len(line.split())
            if n > MAX_WORDS:
                bad.append(f"“{_short(line)}” ({n} words)")
    if bad:
        return _result("words", False, f"Lines over {MAX_WORDS} words: " + "; ".join(bad) + ".")
    return _result("words", True, f"Every text line is {MAX_WORDS} words or fewer.")


def check_safe_area(spec: ExportSpec) -> dict:
    left_limit, right_limit = 0, W - SAFE_RIGHT
    top_limit, bottom_limit = SAFE_TOP, H - SAFE_BOTTOM
    issues = []
    for t in spec.texts:
        lines = t.lines()
        if not lines:
            continue
        pad = border_width(t.size)
        top = t.y - pad
        bottom = t.y + (len(lines) - 1) * line_height(t.size) + t.size * 1.2 + pad
        name = f"“{_short(lines[0])}”"
        if top < top_limit:
            issues.append(f"{name} is too high (top {SAFE_TOP}px is covered)")
        if bottom > bottom_limit:
            issues.append(f"{name} is too low (bottom {SAFE_BOTTOM}px is covered)")
        widest = max(estimate_text_width(ln, t.size) for ln in lines) + 2 * pad
        x0 = t.x if t.x is not None else (W - widest) / 2
        if x0 + widest > right_limit:
            issues.append(f"{name} reaches into the right {SAFE_RIGHT}px (buttons)")
        if x0 < left_limit:
            issues.append(f"{name} runs off the left edge")
    if issues:
        return _result("safe_area", False, "Safe areas: " + "; ".join(issues) + ".")
    return _result("safe_area", True, "All text is inside the safe areas.")


def check_pacing(spec: ExportSpec) -> dict | None:
    texts = [t for t in spec.texts if not is_label(t)]
    if not texts:
        return None
    clip_len = spec.clip_duration
    points = {0.0, clip_len}
    for t in texts:
        points.add(min(max(t.start, 0.0), clip_len))
        points.add(_end(t, clip_len))
    pts = sorted(points)
    gaps = [(b - a, a) for a, b in zip(pts, pts[1:])]
    worst, at = max(gaps)
    if worst > MAX_CHANGE_GAP + 0.01:
        return _result("pacing", False, f"Nothing changes on screen for {worst:.1f} s from "
                       f"{at:.1f} s - aim for a change every 2-4 s.")
    return _result("pacing", True, "Something changes on screen at least every 4 s.")


def check_last_frame(spec: ExportSpec) -> dict:
    if spec.endcard_logo:
        return _result("last_frame", True, "Ends on the clean logo end card.")
    clip_len = spec.clip_duration
    lingering = [t for t in spec.texts if not is_label(t)
                 and _end(t, clip_len) >= clip_len - LAST_FRAME_TOLERANCE]
    if lingering:
        return _result("last_frame", False, f"“{_short(lingering[0].text)}” is still on screen on "
                       "the last frame - end on a clean frame that loops back to the hook.")
    return _result("last_frame", True, "Clean last frame (no text on it).")


def check_privacy() -> dict:
    return _result("privacy", False,
                   "Privacy: check the source frames and the contact sheet for your PSN name, "
                   "wallet, email, redeem codes and notifications.", status="manual")


def check_short(spec: ExportSpec) -> list[dict]:
    """All checks, in the order they matter."""
    results = [check_hook(spec), check_words(spec), check_safe_area(spec), check_length(spec),
               check_last_frame(spec)]
    pacing = check_pacing(spec)
    if pacing:
        results.append(pacing)
    results.append(check_privacy())
    return results
