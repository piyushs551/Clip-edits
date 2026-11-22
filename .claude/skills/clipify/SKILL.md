---
name: clipify
description: "Cut gameplay or other long videos into short vertical clips: find loud or exciting moments, trim, reframe to 9:16, add text overlays. Use for 'clip this', 'make shorts', or a pasted video file."
---

# Clipify (gameplay edition)

Adapted from the MIT-licensed project https://github.com/louisedesadeleer/clipify. Turns a long video into short, social-ready clips for YouTube Shorts, TikTok and Instagram Reels. This version is self-contained: it needs only `ffmpeg`, `ffprobe` and Python with `numpy`. Do not install anything; if a tool is missing, say so and work with what exists.

## Defaults for this user

- Source is usually PS5 gameplay (16:9) or a phone video. Output is 9:16, 1080x1920, 20-40 seconds.
- Text-only: no voiceover and no speech transcription. Use short on-screen text lines (6 words or fewer), bold white with a dark outline, placed mid-screen.
- Never include or leave visible a redeem code, PSN name, email or other account details. Check frames before delivering and blur or crop them out.
- Do not use game trailer footage or game soundtrack as background audio; leave music to be added inside each app at low volume.
- Keep clips spoiler-free for story games.

## Workflow

### 1. Inspect the source
`ffprobe -v error -show_entries stream=width,height,duration,codec_name -of default=nw=1 "$VIDEO"`
Work in `/tmp/clipify/` and write outputs next to the source or to the working directory, never over the original.

### 2. Find candidate moments (action mode)
Extract mono 16 kHz audio and look for loud, sharp moments such as explosions, crashes, gunfire, impacts and crowd reactions.

```bash
mkdir -p /tmp/clipify
ffmpeg -y -i "$VIDEO" -vn -ac 1 -ar 16000 /tmp/clipify/audio.wav
```

Then use a short numpy script: load the wav, compute short-time energy in 50 ms windows, and find peaks above roughly the 95th percentile with a minimum gap of 3-5 seconds between peaks. Keep the 5-8 strongest as candidates. Tune the percentile and gap if there are too many or too few.

Each candidate clip runs from about 4 seconds before the peak to about 8 seconds after, extended if the action continues.

### 3. Verify each candidate is actually on screen
Audio shows a sound happened, not that anything visible did. For each candidate grab a frame at the peak time:
`ffmpeg -y -ss "$T" -i "$VIDEO" -frames:v 1 -vf scale=480:-1 /tmp/clipify/verify_$T.jpg`
Look at each image. Drop candidates that show menus, loading screens, a black frame, a blocked lens, or private details such as account names. Present the remaining candidates with timestamps and a one-line description, and let the user pick.

### 4. Trim
`ffmpeg -y -ss "$START" -t "$DURATION" -i "$VIDEO" -c:v libx264 -crf 20 -preset veryfast -c:a aac /tmp/clipify/clip_N.mp4`
(Re-encode for frame-accurate cuts.)

### 5. Reframe to 9:16
If the source is already vertical, skip this. For 16:9 gameplay, choose one:
- **Center crop (default):** `crop=ih*9/16:ih,scale=1080:1920:flags=lanczos`. Check a frame; if the action is off-center, shift the crop with `crop=ih*9/16:ih:x=OFFSET:y=0`.
- **Blurred-background fit (keeps the whole picture):** split the video, blur and scale one copy to 1080x1920 as the background, scale the other copy to 1080 wide and overlay it centered.

Always export `-pix_fmt yuv420p`, 30 fps, `-c:a aac -b:a 192k`.

### 6. Add text overlays
Use `drawtext` with a bold font that exists on the machine (check with `fc-list`). Style: white text, black border (`borderw=6:bordercolor=black`), centered horizontally, vertically around y=h*0.45 so app buttons don't cover it. One line at a time, shown with `enable='between(t,A,B)'`. Typical pattern: a hook in the first 2 seconds, then one or two supporting lines, then a short call to action such as "Follow for a clip every day."

### 7. Deliver
- Send each finished clip to the user with SendUserFile and give one line each: duration, what happens, what text was added.
- Offer to iterate: different crop position, different text, shorter or longer cut.
- Remind them to pick the background sound inside each app and to upload the same clean file to YouTube, TikTok and Instagram rather than re-uploading a watermarked download.

## Optional: speech clips
If the source has people talking and Whisper is available, transcribe with `whisper audio.wav --model tiny.en --word_timestamps True --output_format json` to find punchlines, then burn word-by-word captions. If Whisper is not installed, skip this and stay in action mode.

## Pitfalls
- Loud is not always interesting: always run the frame check in step 3.
- Re-encode when cutting precisely; `-c copy` can land on the wrong frame.
- For a 4K source, downscale to 1080p first for speed.
- State the plan in one line, then act; do not narrate each iteration.
