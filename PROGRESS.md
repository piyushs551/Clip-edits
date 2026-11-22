# Progress

Living log of what's done, what's next, and what still needs testing on the real Windows laptop.
Updated with every change; newest entries first.

## Status: v1 built, awaiting real-world testing

### Feature checklist (v1)
- [x] 1. Load video by path / file picker; duration, resolution, fps; browser playback with scrubber; 540p preview proxy fallback (export always from original)
- [x] 2. Mark button + `M` key; clip = mark −5 s … +15 s, editable; clip list with thumbnails
- [x] 3. Suggest moments (50 ms windows, >95th percentile, ≥4 s apart, thumbnails; top 30 shown)
- [x] 4. "Blurred Short" 1080×1920 @30 fps: blurred bg, grain, game volume (default 20 %), mute
- [x] 4b. Frame layout: sharp clip stays a full landscape window; zoom 100–150 % magnifies inside it; pan X/Y; vertical clip position; drag / Shift+drag / scroll in the preview
- [x] 5. Text overlays (time range, size, white/red), Poppins Bold + black outline, safe-area preview, saved presets incl. red "DAY 1" label
- [x] 6. Optional end card (logo on navy #1E1B4B, 2.5 s)
- [x] 7. Export: libx264 CRF 18 / 20 Mbps, yuv420p, aac 192k, faststart, dated slug filename, progress bar
- [x] 8. Privacy contact sheet (8 frames) after export
- [x] 9. Freeze last frame 1–2 s
- [x] Error handling: missing ffmpeg (winget hint), bad file, end ≤ start
- [x] Tests: 70 passing (unit + synthetic-clip integration + Flask API)

### Verified so far (Linux, headless)
- Unit + integration tests, including a font path containing a colon and spaces (stand-in for `C:\`)
- Headless-browser run: load → mark → suggest → text/zoom/freeze → export → contact sheet

### Not yet verified
- [ ] Run on Windows 11 with the real `ffmpeg` from winget (setup fixed via `run.bat`, app launch pending confirmation)
- [ ] Real PS5 clip (`.webm` VP9 and `.mp4`), including a long (30–60 min) file for peak-scan and proxy speed
- [ ] `C:\` fontfile escaping in a real Windows run
- [ ] Native file picker (tkinter) on Windows

### Known limitations / ideas for later
- No HDR→SDR tone mapping (HDR captures may look flat)
- Browser text preview approximates ffmpeg rendering; grain not previewed
- Export one clip at a time (no batch export)

## Log

### 2026-11-22 (frame layout)
- Added frame rearranging: vertical clip position (clamped to the frame), zoom that magnifies *inside* the full-landscape window (instead of widening it), horizontal + vertical pan. Preview supports drag, Shift+drag and scroll.
- Tests: filter-string checks plus integration tests that measure where the sharp window lands in a real export (noise clip) and that zoom/pan change the visible content. 70 passing.
- Browser-checked: preview and exported frames agree.

### 2026-11-22 (Windows first run)
- First run on the laptop hit two setup problems: PowerShell blocked `.venv\Scripts\activate` (so `pip` wasn't found) and `python` was older than 3.7 (`future feature annotations` SyntaxError).
- Added `run.bat` (finds Python 3.10+ via `py`, makes the venv, installs deps, starts the app without activation) and rewrote the README setup/troubleshooting.

### 2026-11-22
- Built v1: Flask app, `dailyclip/` pure command builders, web UI, tests, README. Pushed on `claude/beautiful-wozniak-4tvwnj`.
- Workflow change: changes are now committed and merged into `main`; this file is updated with each change.
