# DailyClip Editor

A local, offline tool for turning long gameplay recordings (10–60 min) into vertical 1080×1920 Shorts.
Mark a moment, add text, export. No AI, no API calls, no cost. Runs in your browser; ffmpeg does the work.

## Setup (Windows 11)

1. **Python 3.10+** (older versions fail with `future feature annotations is not defined`):
   ```
   winget install Python.Python.3.12
   ```
   Close and reopen the terminal, then check `py -3.12 --version`.
2. **ffmpeg** (includes ffprobe), then **close and reopen the terminal**:
   ```
   winget install Gyan.FFmpeg
   ```
   Check with `ffmpeg -version`. If it's missing, the app shows this exact install message.
3. Get the code:
   ```
   git clone https://github.com/piyushs551/Clip-edits.git
   cd Clip-edits
   ```

## Run

Easiest (creates `.venv`, installs dependencies, starts the app; no activation needed):
```
.\run.bat
```

Or by hand, without activating anything (this avoids PowerShell's "running scripts is disabled" error):
```
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```
Your browser opens at http://127.0.0.1:5000. Stop with Ctrl+C. Nothing leaves your machine.

Troubleshooting:
- *"running scripts is disabled"* when activating the venv: don't activate; use `run.bat` or the `.venv\Scripts\python.exe` form above.
- *`pip` is not recognized*: use `python -m pip ...` (or the venv form above).
- *`future feature annotations is not defined`*: your `python` is too old. Install 3.12 as above, delete the `.venv` folder, and run `run.bat`.

Exports go to `projects\exports\` (set `DAILYCLIP_OUT` to change; `DAILYCLIP_DATA` moves all working files).

## Using it

1. **Load** a video: paste the path (quotes from Explorer's *Copy as path* are fine) or press *Browse…*.
   Duration, resolution and fps are shown. If the browser can't play the codec, a 540p preview proxy is built
   automatically — **preview only; exports always read the original**.
2. **Mark** moments with the button or **M**. Each mark makes a clip from *mark − 5 s* to *mark + 15 s*; edit start/end
   (type seconds or `m:ss`, or use *⇤/⇥ playhead*). Keys: Space play/pause, ←/→ ±5 s (Shift = 1 s).
3. **Suggest moments** (optional): scans audio for loud peaks (50 ms windows, above the 95th percentile, ≥ 4 s apart,
   strongest 30 shown) with thumbnails. Loud isn't always interesting — press *Keep* only on the ones you want.
4. **Blurred Short** template: blurred+darkened background (boxblur 30:5, brightness −0.15, optional film grain),
   sharp foreground at 1080 wide with 100–150 % zoom, game volume (default 20 %) or mute. The middle panel is a live
   9:16 preview with the **safe areas** shaded (top 150 px, bottom 400 px, right 150 px).
5. **Text**: Poppins Bold (bundled; falls back to Arial Bold / DejaVu), black outline, centered, default y = 250.
   White or red `#FF5A5F`. Presets are saved to `projects/presets.json` and include a small red **DAY 1** top-left label.
6. **End card** (optional): your logo on navy `#1E1B4B` for 2.5 s. **Freeze** holds the last frame 1–2 s.
7. **Export**: libx264 CRF 18 (or 20 Mbps), yuv420p, AAC 192k, faststart, no watermark →
   `YYYY-MM-DD_name.mp4`. A **contact sheet** of 8 frames appears afterwards — check it for your PSN name,
   notifications, trophy pop-ups and chat before posting.

Clips, text and settings are remembered per video in your browser (localStorage).

## Project status

See [PROGRESS.md](PROGRESS.md) for the feature checklist, what is verified, and the change log.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest
```
Unit tests cover the ffmpeg command/filter builders (including Windows `C:\` path escaping), validation and peak
detection. The integration test generates a 10 s synthetic clip with ffmpeg and exports it, then checks the result with
ffprobe (1080×1920, 30 fps, H.264, yuv420p, AAC, faststart, duration with freeze + end card). It's skipped if ffmpeg is absent.

## Layout

```
run.bat                Windows launcher (venv + deps + start)
app.py                 Flask server + background jobs
dailyclip/commands.py  pure ffmpeg command / filtergraph builders (+ validation)
dailyclip/probe.py     ffprobe wrapper, browser-playability check
dailyclip/peaks.py     loud-moment detection (numpy)
dailyclip/presets.py   text-style presets (JSON)
dailyclip/runner.py    runs ffmpeg, parses progress
templates/ static/     the web UI (plain HTML/JS/CSS) + bundled Poppins Bold (OFL)
tests/                 pytest suite
```

## Notes / limitations (v1)

- **PS5 captures**: the PS5 saves clips as `.webm` (VP9) by default, or `.mp4` if you change *Settings → Captures →
  Video Clip Format*. Both work. Copy them off a USB drive or use the PS App/USB; you can load straight from the drive.
- HDR captures (10-bit) export fine but colours may look flat; v1 does no HDR→SDR tone-mapping.
- Text is drawn as one centered line per row; the browser preview approximates ffmpeg's rendering.
- Not in v1: captions/speech-to-text, AI moment detection, posting to platforms, cloud.
- Font: Poppins Bold is © The Poppins Project Authors, SIL Open Font License (`static/fonts/OFL.txt`).
