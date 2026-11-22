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
- [x] 7. Export: libx264 Best (CRF 14) / CRF 18 / 20 Mbps, 30 or 60 fps, yuv420p, aac 192k, faststart, dated slug filename, progress bar
- [x] 8. Privacy contact sheet (8 frames) after export, plus a source-frame sheet before export and a confirmation tick
- [x] 10. DailyClip rule checklist (hook, <=6 words, safe areas, <30 s, pacing, clean last frame)
- [x] 9. Freeze last frame 1–2 s
- [x] Error handling: missing ffmpeg (winget hint), bad file, end ≤ start
- [x] Tests: 95 passing (unit + synthetic-clip integration + Flask API)

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

### 2026-11-22 (DailyClip rules built in)
- Added the three channel skills to `.claude/skills/` (shorts-packaging, clipify, dailyclip-workflow) and a section in `CLAUDE.md` so they are followed when planning/changing the app.
- New `dailyclip/checks.py` + live **Short checklist** in the UI: hook on frame one / within 3 s, lines <= 6 words, safe areas (top 150, bottom 400, right 150; width estimated from measured Poppins Bold metrics), under 30 s, change every 2-4 s, clean last frame. Advisory only.
- Privacy: **Check source frames** (contact sheet of the clip's source footage, before export) + confirmation tick; export asks if it isn't ticked. Post-export contact sheet unchanged.
- Default export quality is now 20 Mbps (your preference, from the original file); Best (CRF 14) and Good (CRF 18) remain.

### 2026-11-22 (quality)
- Crispness pass: default quality is now *Best* (x264 CRF 14, preset slow, High profile), Lanczos resize for the sharp clip, BT.709 colour tags, GOP = 2 s, optional 60 fps output (30 stays default). "Good" (CRF 18) and 20 Mbps remain selectable.
- Tips for upload: upload the MP4 directly (not a screen recording), 1080x1920; 60 fps for fast gameplay.

### 2026-11-22 (frame layout)
- Added frame rearranging: vertical clip position (clamped to the frame), zoom that magnifies *inside* the full-landscape window (instead of widening it), horizontal + vertical pan. Preview supports drag, Shift+drag and scroll.
- Tests: filter-string checks plus integration tests that measure where the sharp window lands in a real export (noise clip) and that zoom/pan change the visible content. 95 passing.
- Browser-checked: preview and exported frames agree.

### 2026-11-22 (Windows first run)
- First run on the laptop hit two setup problems: PowerShell blocked `.venv\Scripts\activate` (so `pip` wasn't found) and `python` was older than 3.7 (`future feature annotations` SyntaxError).
- Added `run.bat` (finds Python 3.10+ via `py`, makes the venv, installs deps, starts the app without activation) and rewrote the README setup/troubleshooting.

### 2026-11-22
- Built v1: Flask app, `dailyclip/` pure command builders, web UI, tests, README. Pushed on `claude/beautiful-wozniak-4tvwnj`.
- Workflow change: changes are now committed and merged into `main`; this file is updated with each change.
