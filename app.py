"""DailyClip Editor - local Flask app. Run:  python app.py"""
from __future__ import annotations

import dataclasses
import os
import shutil
import subprocess
import sys
import threading
import uuid
import webbrowser
from pathlib import Path

from werkzeug.exceptions import HTTPException
from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

from dailyclip import commands, peaks, presets
from dailyclip.probe import probe
from dailyclip.runner import run_simple, run_with_progress
from dailyclip.util import (BASE_DIR, BadFileError, DailyClipError, FFmpegFailed,
                            clean_user_path, ffmpeg_status, find_font, output_name,
                            require_ffmpeg, unique_path)

DATA_DIR = Path(os.environ.get("DAILYCLIP_DATA", BASE_DIR / "projects"))
THUMBS = DATA_DIR / "thumbs"
PROXIES = DATA_DIR / "proxies"
EXPORTS = Path(os.environ.get("DAILYCLIP_OUT", DATA_DIR / "exports"))
TMP = DATA_DIR / "tmp"
PRESET_FILE = DATA_DIR / "presets.json"
for d in (THUMBS, PROXIES, EXPORTS, TMP):
    d.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

STATE: dict = {"video": None, "proxy": None}
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


# --------------------------------------------------------------------------
# errors
# --------------------------------------------------------------------------
@app.errorhandler(DailyClipError)
def handle_known(e: DailyClipError):
    return jsonify(error=str(e), code=e.code), e.status


@app.errorhandler(Exception)
def handle_unknown(e: Exception):
    if isinstance(e, HTTPException):
        return jsonify(error=e.description, code=e.name.lower().replace(" ", "_")), e.code
    app.logger.exception("Unhandled error")
    return jsonify(error=f"Unexpected error: {e}", code="unexpected"), 500


# --------------------------------------------------------------------------
# jobs (background threads, polled by the UI)
# --------------------------------------------------------------------------
def start_job(kind: str, fn) -> str:
    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {"id": job_id, "kind": kind, "state": "running", "progress": 0.0,
                    "result": None, "error": None}

    def progress(p: float):
        JOBS[job_id]["progress"] = round(p, 4)

    def runner():
        try:
            JOBS[job_id]["result"] = fn(progress)
            JOBS[job_id].update(state="done", progress=1.0)
        except DailyClipError as e:
            JOBS[job_id].update(state="error", error=str(e))
        except Exception as e:  # noqa: BLE001
            app.logger.exception("job failed")
            JOBS[job_id].update(state="error", error=f"Unexpected error: {e}")

    threading.Thread(target=runner, daemon=True).start()
    return job_id


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify(error="Unknown job.", code="not_found"), 404
    return jsonify(job)


# --------------------------------------------------------------------------
# pages / static media
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    st = ffmpeg_status()
    st["output_dir"] = str(EXPORTS)
    try:
        st["font"] = find_font()
    except DailyClipError as e:
        st["font"] = None
        st["font_warning"] = str(e)
    return jsonify(st)


@app.get("/media/video")
def media_video():
    """Preview stream (proxy when present). Supports HTTP range requests."""
    which = request.args.get("which", "auto")
    video, proxy = STATE["video"], STATE["proxy"]
    if not video:
        return jsonify(error="No video loaded."), 404
    path = proxy if (proxy and which != "original") else video["path"]
    return send_file(path, conditional=True)


@app.get("/media/thumbs/<path:name>")
def media_thumb(name):
    return send_from_directory(THUMBS, name)


@app.get("/media/exports/<path:name>")
def media_export(name):
    return send_from_directory(EXPORTS, name)


# --------------------------------------------------------------------------
# load video
# --------------------------------------------------------------------------
@app.post("/api/load")
def load_video():
    require_ffmpeg()
    path = clean_user_path((request.get_json(silent=True) or {}).get("path", ""))
    if not path:
        raise BadFileError("Enter or pick a video file first.")
    info = probe(path)
    STATE["video"], STATE["proxy"] = info, None
    # reuse an existing proxy from a previous session
    existing = _proxy_path(info)
    if not info["browser_playable"] and existing.is_file():
        STATE["proxy"] = str(existing)
    info = dict(info, needs_proxy=not info["browser_playable"] and not STATE["proxy"],
                has_proxy=bool(STATE["proxy"]), key=_key(info))
    return jsonify(info)


def _key(info: dict) -> str:
    st = Path(info["path"]).stat()
    return f"{Path(info['path']).name}-{st.st_size}-{int(st.st_mtime)}"


def _proxy_path(info: dict) -> Path:
    return PROXIES / f"{_slug_key(info)}.mp4"


def _slug_key(info: dict) -> str:
    return "".join(c if c.isalnum() else "_" for c in _key(info))


@app.post("/api/proxy")
def make_proxy():
    """Generate a 540p preview proxy (preview only - exports use the original)."""
    video = _need_video()
    dst = _proxy_path(video)
    tmp = dst.with_suffix(".part.mp4")

    def work(progress):
        cmd = commands.build_proxy_cmd(video["path"], str(tmp))
        run_with_progress(cmd, video["duration"], progress)
        tmp.replace(dst)
        STATE["proxy"] = str(dst)
        return {"proxy": True}

    return jsonify(job=start_job("proxy", work))


def _need_video() -> dict:
    if not STATE["video"]:
        raise BadFileError("Load a video first.")
    return STATE["video"]


# --------------------------------------------------------------------------
# file picker (tkinter in a subprocess, so it can't block/crash Flask)
# --------------------------------------------------------------------------
PICKER_CODE = r"""
import sys
import tkinter as tk
from tkinter import filedialog
kind = sys.argv[1]
types = {
    "video": [("Video", "*.mp4 *.mkv *.mov *.webm *.avi *.m4v *.ts"), ("All files", "*.*")],
    "image": [("Image", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")],
}[kind]
root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
print(filedialog.askopenfilename(filetypes=types))
"""


@app.post("/api/pick")
def pick_file():
    kind = (request.get_json(silent=True) or {}).get("kind", "video")
    if kind not in ("video", "image"):
        kind = "video"
    try:
        res = subprocess.run([sys.executable, "-c", PICKER_CODE, kind],
                             capture_output=True, text=True, timeout=600)
    except Exception:  # noqa: BLE001
        res = None
    if not res or res.returncode != 0:
        raise DailyClipError("The file picker isn't available here - paste the file path instead.")
    return jsonify(path=res.stdout.strip())


# --------------------------------------------------------------------------
# thumbnails + suggestions
# --------------------------------------------------------------------------
def make_thumb(video: dict, t: float) -> str:
    name = f"{_slug_key(video)}_{int(round(t * 1000))}.jpg"
    dst = THUMBS / name
    if not dst.is_file():
        run_simple(commands.build_thumbnail_cmd(video["path"], t, str(dst)), timeout=60)
    return f"/media/thumbs/{name}"


@app.post("/api/thumb")
def thumb():
    video = _need_video()
    t = float((request.get_json(silent=True) or {}).get("t", 0))
    t = min(max(0.0, t), max(0.0, video["duration"] - 0.1))
    return jsonify(url=make_thumb(video, t))


@app.post("/api/suggest")
def suggest():
    video = _need_video()
    if not video["has_audio"]:
        raise BadFileError("This video has no audio track, so there are no loud moments to find.")
    max_peaks = int((request.get_json(silent=True) or {}).get("max", 30))

    def work(progress):
        found = peaks.suggest_moments(video["path"], max_peaks=max(1, min(max_peaks, 100)))
        progress(0.3)
        for i, p in enumerate(found):
            p["thumb"] = make_thumb(video, p["time"])
            progress(0.3 + 0.7 * (i + 1) / len(found))
        return {"peaks": found}

    return jsonify(job=start_job("suggest", work))


# --------------------------------------------------------------------------
# presets
# --------------------------------------------------------------------------
@app.get("/api/presets")
def get_presets():
    return jsonify(presets.load_presets(PRESET_FILE))


@app.post("/api/presets")
def post_preset():
    body = request.get_json(silent=True) or {}
    return jsonify(presets.save_preset(PRESET_FILE, body.get("name", ""), body.get("style", {})))


@app.delete("/api/presets/<path:name>")
def del_preset(name):
    return jsonify(presets.delete_preset(PRESET_FILE, name))


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------
@app.post("/api/export")
def export():
    require_ffmpeg()
    video = _need_video()
    body = request.get_json(silent=True) or {}
    body["src"] = video["path"]          # always export from the ORIGINAL
    body["endcard_logo"] = clean_user_path(body.get("endcard_logo") or "") or None
    spec = commands.spec_from_dict(body, video["duration"], video["has_audio"])
    find_font()                           # fail early with a clear message

    out_path = unique_path(EXPORTS / output_name(body.get("slug") or "short"))
    work_dir = TMP / uuid.uuid4().hex[:8]

    def work(progress):
        try:
            texts = commands.write_text_files(spec.texts, work_dir)
            final = dataclasses.replace(spec, texts=texts)
            cmd = commands.build_export_cmd(final, str(out_path))
            run_with_progress(cmd, final.total_duration, lambda p: progress(p * 0.95))
            sheet = out_path.with_suffix(".contact.jpg")
            made = make_contact_sheet(out_path, sheet)
            return {"file": out_path.name, "path": str(out_path),
                    "url": f"/media/exports/{out_path.name}",
                    "contact_sheet": f"/media/exports/{sheet.name}" if made else None}
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    return jsonify(job=start_job("export", work))


def make_contact_sheet(video_path: Path, dst: Path) -> bool:
    try:
        info = probe(str(video_path))
        run_simple(commands.build_contact_sheet_cmd(str(video_path), str(dst),
                                                    info["duration"], 8), timeout=120)
        return dst.is_file()
    except DailyClipError:
        return False


@app.post("/api/contact-sheet")
def contact_sheet():
    """Regenerate the privacy contact sheet for an exported file."""
    name = (request.get_json(silent=True) or {}).get("file", "")
    path = EXPORTS / Path(name).name
    if not path.is_file():
        raise BadFileError("That export no longer exists.")
    sheet = path.with_suffix(".contact.jpg")
    if not make_contact_sheet(path, sheet):
        raise FFmpegFailed("Couldn't build the contact sheet.")
    return jsonify(url=f"/media/exports/{sheet.name}")


def main():
    st = ffmpeg_status()
    if not st["ok"]:
        print("\n*** " + st["message"] + "\n", file=sys.stderr)
    host, port = "127.0.0.1", int(os.environ.get("PORT", 5000))
    if os.environ.get("DAILYCLIP_NO_BROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    print(f"DailyClip Editor running at http://{host}:{port}  (Ctrl+C to quit)")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
