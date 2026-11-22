# Working agreement for this repo

- After each piece of work: commit, then merge into `main` and push `main` (the owner has authorised this).
  Develop on the session branch, then fast-forward/merge to `main`. Don't open PRs unless asked.
- Keep `PROGRESS.md` current with every change (checklist, verified/unverified, dated log entry).
  Update `README.md` when setup, usage or behaviour changes.
- Run `python -m pytest` before committing.
- Target is Windows 11; keep ffmpeg paths, quoting and drawtext (textfile + escaped fontfile) Windows-safe.
- v1 stays offline: no AI/API calls, no cloud, no captions.
