---
name: dailyclip-workflow
description: "End-to-end routine for a DailyClip short video: plan, build the vertical video from the user's clips, then hand over the video plus posting kits for YouTube, TikTok and Instagram."
---

# DailyClip video workflow

Use when the user shares clips or screenshots and wants a finished short video, or says "kit" for the next day's post. This skill is the checklist. It loads two other skills in order: `shorts-packaging` for the words, and `clipify` for the video build. Load each with the Skill tool when its step starts.

## Channel facts
- Channel: DailyClip. Handles: new.dailyclip on Instagram and YouTube; TikTok may still be a numbered handle.
- Separate Gmail and separate accounts from the user's personal ones. Never suggest linking them (no Facebook sharing, no contact sync).
- Look: navy #1E1B4B background, red #FF5A5F accent, Poppins Bold text, clapperboard-and-controller logo as the end card.
- GTA 6 launches Nov 19, 2026 on PlayStation. The user is on PS5 and posts by hand from the phone.
- Text-only videos: no voiceover and no speaking.

## Steps

1. **Intake (one message at most).** Find out what the video is and what footage exists. If the footage or topic is clear, do not ask; state the plan in one line and start. Attached video and image files are in the attachments folder; read them directly.

2. **Plan with `shorts-packaging`.** Pick the hook, write the on-screen text table (6 words or fewer per line), and choose the title. Check that any date-relative wording is right for the posting day.

3. **Privacy check on every source.** Look at frames from every clip and every screenshot. Remove or skip anything showing a PSN or account name, wallet balance, email, redeem code, address or other personal detail. Redeemed codes and account panels in store screenshots are the usual problems. Crop or leave those shots out.

4. **Build with `clipify`.** Normalize each segment to 1080x1920 at 30 fps (phone clips with rotation metadata may need a transpose; verify against a frame). Screenshots go on a blurred background and are cropped in to the important region so text is readable. Add the text with drawtext using text files (not inline text, because a colon breaks the filter). Finish with the logo end card. Keep it about 15 to 30 seconds.

5. **Check the result.** Export a contact sheet of frames at the middle of each text window and look at it: text readable and inside the safe area, nothing private, nothing cut off, duration and size correct. Fix and re-render before delivering.

6. **Deliver.** Send the video file with a short caption. Then give one kit per app using `shorts-packaging`: YouTube (title, description, settings), TikTok (caption, settings, sound search terms), Instagram (caption, settings including Facebook sharing OFF, alt text). Add the first comment text and a reminder to reply to early comments.

7. **Follow up.** Next day, ask for views on each app, name the best performer, and set the next video's angle. Offer tomorrow's plan.

## Planned launch-week sequence (adjust to what the user posts)
- Sun Nov 15: unboxing (done)
- Mon Nov 16: 5 things to know before GTA 6 drops
- Tue Nov 17: preload and setup tips
- Wed Nov 18: countdown teaser
- Thu Nov 19: launch day, first-hour reaction and first gameplay clip
- Then: one Daily Clip and one Quick Tip each day

## Rules
- Do not install packages; network access may be off. Use ffmpeg, ffprobe and Python with numpy only.
- Do not use trailer footage or the game's soundtrack. Music is added by the user inside each app.
- Upload the same clean file to every app; never re-upload a copy downloaded from TikTok.
- Never publish for the user; posting is done by hand unless they connect a scheduling tool later.
