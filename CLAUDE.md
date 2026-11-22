# Working agreement for this repo

## Workflow
- After each piece of work: commit, then merge into `main` and push `main` (the owner has authorised this).
  Develop on the session branch, then fast-forward/merge to `main`. Don't open PRs unless asked.
- Keep `PROGRESS.md` current with every change (checklist, verified/unverified, dated log entry).
  Update `README.md` when setup, usage or behaviour changes.
- Run `python -m pytest` before committing.
- Target is Windows 11; keep ffmpeg paths, quoting and drawtext (textfile + escaped fontfile) Windows-safe.
- v1 stays offline: no AI/API calls, no cloud, no captions.

## DailyClip skills - follow them when planning or changing the app
The channel's three skills live in `.claude/skills/` (copies of the ones used in claude.ai):
- `shorts-packaging` - the words: hook in the first 3 s, text on frame one, <= 6 words per line, change something
  every 2-4 s, clean last frame that loops to the hook, titles/captions/hashtags, per-app settings.
- `clipify` - the video build: audio-energy moments (50 ms windows, ~95th percentile), verify with a real frame,
  re-encode trims, blurred-background 9:16 fit, drawtext from text files, yuv420p / aac / high bitrate.
- `dailyclip-workflow` - the checklist: plan -> privacy check every source -> build -> contact sheet -> deliver -> review.

Read the relevant skill before planning or changing a feature it covers, and keep the app consistent with it.
Brand: navy #1E1B4B, red #FF5A5F, Poppins Bold, logo end card. Output 1080x1920, 30 fps, one file for all 3 apps.

### Rules built into the app (keep them working; `dailyclip/checks.py`)
- Hook text on frame one / within the first 3 s (a positioned label like "DAY 1" doesn't count as a hook).
- Text lines of 6 words or fewer.
- Text outside the safe areas: top 150 px, bottom 400 px, right 150 px.
- Short under 30 seconds (clip + freeze + end card).
- Something changes on screen every 2-4 s; clean last frame (or the logo end card).
- Privacy: source-frame contact sheet before export + contact sheet after export; the user ticks a confirmation.
- Defaults: blurred-background layout with little zoom (100 %), export from the ORIGINAL at ~20 Mbps (default),
  30 fps, game audio 20 %.
- Checks are advisory (warnings, never blockers), except the privacy confirmation prompt.
