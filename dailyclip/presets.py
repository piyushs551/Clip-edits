"""Text-style presets saved as JSON."""
from __future__ import annotations

import json
from pathlib import Path

from .util import ValidationError

DEFAULTS = {
    "Hook - white (top)": {"size": 72, "color": "white", "x": None, "y": 250, "start": 0, "end": 4},
    "Hook - red (top)": {"size": 72, "color": "red", "x": None, "y": 250, "start": 0, "end": 4},
    "DAY 1 label": {"size": 40, "color": "red", "x": 60, "y": 170, "start": 0, "end": None,
                    "text": "DAY 1"},
}
FIELDS = ("text", "size", "color", "x", "y", "start", "end")


def load_presets(path: Path) -> dict:
    presets = {k: dict(v) for k, v in DEFAULTS.items()}
    try:
        presets.update(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        pass
    return presets


def save_preset(path: Path, name: str, style: dict) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValidationError("Give the preset a name.")
    path = Path(path)
    try:
        custom = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        custom = {}
    custom[name] = {k: style.get(k) for k in FIELDS if k in style}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(custom, indent=2), encoding="utf-8")
    return load_presets(path)


def delete_preset(path: Path, name: str) -> dict:
    path = Path(path)
    try:
        custom = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        custom = {}
    custom.pop(name, None)
    if path.parent.exists():
        path.write_text(json.dumps(custom, indent=2), encoding="utf-8")
    return load_presets(path)
