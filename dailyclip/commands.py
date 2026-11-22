"""Pure functions that build ffmpeg argument lists / filtergraphs.

Nothing in this module touches the disk or runs a process (except
`write_text_files`, the one explicit helper that writes drawtext textfiles),
so everything else can be unit-tested by looking at the strings.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .util import ValidationError

W, H, FPS = 1080, 1920, 30      # FPS = default output frame rate
FPS_CHOICES = (30, 60)
NAVY = "1E1B4B"
RED = "#FF5A5F"
SAFE_TOP, SAFE_BOTTOM, SAFE_RIGHT = 150, 400, 150
MAX_FREEZE = 2.0
ENDCARD_SECS = 2.5

COLORS = {"white": "white", "red": RED}


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@dataclass
class TextOverlay:
    text: str
    start: float = 0.0          # seconds, relative to clip start
    end: Optional[float] = None  # None = until end of clip
    size: int = 64
    color: str = "white"        # "white", "red" or "#RRGGBB"
    x: Optional[int] = None     # None = centered
    y: int = 250
    textfiles: list = field(default_factory=list)  # one per non-empty line

    def lines(self) -> list[str]:
        return [ln for ln in self.text.replace("\r", "").split("\n") if ln.strip()]


@dataclass
class ExportSpec:
    src: str
    start: float
    end: float
    zoom: float = 1.0
    fg_y: int = 0               # vertical offset of the sharp clip in output px (+ = down)
    pan: float = 0.0            # -1 (left) .. 1 (right): which part shows when zoomed
    pan_y: float = 0.0          # -1 (top) .. 1 (bottom): same, vertically
    volume: float = 0.20        # 0..1
    mute: bool = False
    grain: int = 0              # 0 = off, noise strength otherwise
    has_audio: bool = True
    texts: list = field(default_factory=list)
    endcard_logo: Optional[str] = None
    endcard_secs: float = ENDCARD_SECS
    freeze: float = 0.0
    quality: str = "best"       # "best" (CRF 14, slow) | "crf" (CRF 18) | "bitrate" (20 Mbps)
    fps: int = FPS              # output frame rate: 30 or 60
    font: Optional[str] = None

    @property
    def clip_duration(self) -> float:
        return self.end - self.start

    @property
    def total_duration(self) -> float:
        extra = self.endcard_secs if self.endcard_logo else 0.0
        return self.clip_duration + self.freeze + extra


def spec_from_dict(d: dict, src_duration: float | None = None,
                   has_audio: bool = True) -> ExportSpec:
    """Build + validate an ExportSpec from untrusted JSON (the web UI)."""

    def num(key, default=None, minimum=None, maximum=None, label=None):
        label = label or key
        v = d.get(key, default)
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise ValidationError(f"'{label}' must be a number.")
        if minimum is not None and v < minimum:
            raise ValidationError(f"'{label}' must be at least {minimum:g}.")
        if maximum is not None and v > maximum:
            raise ValidationError(f"'{label}' must be at most {maximum:g}.")
        return v

    start = num("start", label="Start time", minimum=0)
    end = num("end", label="End time", minimum=0)
    if end <= start:
        raise ValidationError(
            f"End time ({end:.2f}s) must be after start time ({start:.2f}s)."
        )
    if src_duration is not None:
        if start >= src_duration:
            raise ValidationError(
                f"Start time ({start:.2f}s) is past the end of the video ({src_duration:.2f}s)."
            )
        if end > src_duration + 0.05:
            raise ValidationError(
                f"End time ({end:.2f}s) is past the end of the video ({src_duration:.2f}s)."
            )
    clip_len = end - start
    zoom = num("zoom", 1.0, 1.0, 1.5, "Zoom")
    fg_y = int(num("fg_y", 0, -H // 2, H // 2, "Vertical position"))
    pan = num("pan", 0.0, -1.0, 1.0, "Horizontal pan")
    pan_y = num("pan_y", 0.0, -1.0, 1.0, "Vertical pan")
    volume = num("volume", 0.2, 0.0, 1.0, "Game volume")
    grain = int(num("grain", 0, 0, 50, "Film grain"))
    freeze = num("freeze", 0.0, 0.0, MAX_FREEZE, "Freeze")
    quality = d.get("quality", "best")
    if quality not in ("best", "crf", "bitrate"):
        raise ValidationError("Quality must be 'best', 'crf' or 'bitrate'.")
    fps = int(num("fps", FPS, 1, 120, "Frame rate"))
    if fps not in FPS_CHOICES:
        raise ValidationError("Frame rate must be 30 or 60.")

    logo = d.get("endcard_logo") or None
    if logo and not Path(logo).is_file():
        raise ValidationError(f"End-card logo not found: {logo}")

    texts = []
    for i, t in enumerate(d.get("texts") or [], 1):
        text = str(t.get("text", ""))
        if not text.strip():
            continue
        t_start = float(t.get("start") or 0)
        t_end = t.get("end")
        t_end = clip_len if t_end in (None, "") else float(t_end)
        if t_end <= t_start:
            raise ValidationError(
                f"Text line {i}: end ({t_end:.2f}s) must be after start ({t_start:.2f}s)."
            )
        size = int(t.get("size") or 64)
        if not 12 <= size <= 300:
            raise ValidationError(f"Text line {i}: font size must be between 12 and 300.")
        color = str(t.get("color") or "white")
        color = COLORS.get(color, color)
        if color != "white" and not _is_hex_color(color):
            raise ValidationError(f"Text line {i}: color must be white, red or #RRGGBB.")
        x = t.get("x")
        texts.append(TextOverlay(
            text=text, start=t_start, end=t_end, size=size, color=color,
            x=None if x in (None, "") else int(x),
            y=int(t.get("y") if t.get("y") not in (None, "") else 250),
        ))

    return ExportSpec(
        src=str(d.get("src", "")), start=start, end=end, zoom=zoom, fg_y=fg_y, pan=pan, pan_y=pan_y, volume=volume,
        mute=bool(d.get("mute")), grain=grain, has_audio=has_audio, texts=texts,
        endcard_logo=logo, freeze=freeze, quality=quality, fps=fps,
    )


def _is_hex_color(c: str) -> bool:
    c = c.lstrip("#")
    return len(c) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in c)


# --------------------------------------------------------------------------
# Escaping / formatting
# --------------------------------------------------------------------------
def fmt(x: float) -> str:
    """Trim-friendly float formatting for ffmpeg."""
    return f"{x:.3f}".rstrip("0").rstrip(".") or "0"


def escape_filter_path(p: str) -> str:
    """Quote a file path for use as a filter option value.

    Windows: backslashes -> '/', and the drive colon (C:/...) becomes C\\:/...
    The value is wrapped in single quotes so spaces survive.
    """
    p = str(p).replace("\\", "/")
    p = p.replace(":", "\\:")
    p = p.replace("'", "'\\\\\\''")
    return f"'{p}'"


def ffmpeg_color(c: str) -> str:
    return "0x" + c[1:] if c.startswith("#") else c


def border_width(size: int) -> int:
    return max(3, round(size * 0.09))


def line_height(size: int) -> int:
    return round(size * 1.3)


# --------------------------------------------------------------------------
# drawtext textfiles (the only function here that writes to disk)
# --------------------------------------------------------------------------
def write_text_files(texts: list[TextOverlay], directory: str | Path) -> list[TextOverlay]:
    """Write one UTF-8 textfile per non-empty line; return updated overlays.

    Text is always passed to drawtext via textfile= (never inline) because
    colons, quotes and percent signs break inline filter text.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    out = []
    for i, t in enumerate(texts):
        files = []
        for j, line in enumerate(t.lines()):
            f = directory / f"text_{i}_{j}.txt"
            f.write_text(line, encoding="utf-8")  # no trailing newline
            files.append(str(f))
        out.append(dataclasses.replace(t, textfiles=files))
    return out


# --------------------------------------------------------------------------
# Filtergraph
# --------------------------------------------------------------------------
def drawtext_filters(texts: list[TextOverlay], font: str) -> list[str]:
    filters = []
    for t in texts:
        lines = t.lines()
        if len(t.textfiles) != len(lines):
            raise ValueError("Call write_text_files() before building the command.")
        end = t.end if t.end is not None else 1e6
        for j, tf in enumerate(t.textfiles):
            x = "(w-text_w)/2" if t.x is None else str(int(t.x))
            y = int(t.y) + j * line_height(t.size)
            filters.append(
                "drawtext="
                f"fontfile={escape_filter_path(font)}:"
                f"textfile={escape_filter_path(tf)}:"
                "expansion=none:"
                f"fontsize={int(t.size)}:"
                f"fontcolor={ffmpeg_color(t.color)}:"
                f"borderw={border_width(t.size)}:bordercolor=black:"
                f"x={x}:y={y}:"
                f"enable='between(t,{fmt(t.start)},{fmt(end)})'"
            )
    return filters


def build_filter_graph(spec: ExportSpec) -> tuple[str, str, str]:
    """Return (filter_complex, video_label, audio_label)."""
    from .util import find_font  # lazy: only needed when text is present

    dur, frz = spec.clip_duration, spec.freeze
    main_total = dur + frz
    g: list[str] = []

    # --- video: blurred background + sharp (zoomable) foreground -----------
    g.append(f"[0:v]fps={spec.fps},setsar=1,split=2[bgin][fgin]")
    bg = (f"[bgin]scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H},boxblur=30:5,eq=brightness=-0.15")
    if spec.grain > 0:
        bg += f",noise=alls={int(spec.grain)}:allf=t+u"
    g.append(bg + "[bg]")

    fg_w = int(round(W * spec.zoom / 2.0)) * 2
    # lanczos = sharpest resampling; zoom is applied in this single resize (no double resampling)
    fg = f"[fgin]scale={fg_w}:-2:flags=lanczos+accurate_rnd+full_chroma_int"
    if fg_w > W:
        # Zoom INTO the picture: the sharp clip keeps its full landscape window
        # (1080 wide, original aspect), the content inside is magnified and
        # panned by pan / pan_y (0 = centered).
        fx = (max(-1.0, min(1.0, spec.pan)) + 1) / 2
        fy = (max(-1.0, min(1.0, spec.pan_y)) + 1) / 2
        fg += (f",crop={W}:trunc(ih*{W}/iw/2)*2:"
               f"x=(iw-ow)*{fx:.4f}:y=(ih-oh)*{fy:.4f}")
    g.append(fg + "[fg]")
    # centered by default; fg_y moves it, clamped so the clip stays inside the frame
    y = f"(H-h)/2+({int(spec.fg_y)})"
    g.append(f"[bg][fg]overlay=(W-w)/2:min(max(0\\,{y})\\,H-h):format=auto[v0]")


    chain = ["setsar=1", "format=yuv420p"]
    if spec.texts:
        chain += drawtext_filters(spec.texts, spec.font or find_font())
    if frz > 0:
        chain.append(f"tpad=stop_mode=clone:stop_duration={fmt(frz)}")
    g.append("[v0]" + ",".join(chain) + "[vmain]")

    # --- audio: game volume (the blurred background copy has no audio) -----
    if spec.has_audio and not spec.mute:
        g.append(
            "[0:a:0]aresample=48000,aformat=channel_layouts=stereo,"
            f"volume={spec.volume:.3f},apad=whole_dur={fmt(main_total)},"
            f"atrim=duration={fmt(main_total)},asetpts=N/SR/TB[amain]"
        )
    else:
        g.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={fmt(main_total)},"
                 "asetpts=N/SR/TB[amain]")

    # --- optional end card: logo on navy -----------------------------------
    if spec.endcard_logo:
        s = fmt(spec.endcard_secs)
        g.append(f"color=c=0x{NAVY}:s={W}x{H}:r={spec.fps}:d={s}[navy]")
        g.append("[1:v]format=rgba,scale=w=800:h=800:force_original_aspect_ratio=decrease[logo]")
        g.append("[navy][logo]overlay=(W-w)/2:(H-h)/2:shortest=1,"
                 f"fps={spec.fps},setsar=1,format=yuv420p[vend]")
        g.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={s},asetpts=N/SR/TB[aend]")
        g.append("[vmain][amain][vend][aend]concat=n=2:v=1:a=1[vout][aout]")
        return ";".join(g), "[vout]", "[aout]"
    return ";".join(g), "[vmain]", "[amain]"


# --------------------------------------------------------------------------
# Command builders
# --------------------------------------------------------------------------
def build_export_cmd(spec: ExportSpec, out_path: str, ffmpeg: str = "ffmpeg") -> list[str]:
    graph, vlabel, alabel = build_filter_graph(spec)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
           "-ss", fmt(spec.start), "-t", fmt(spec.clip_duration), "-i", str(spec.src)]
    if spec.endcard_logo:
        cmd += ["-loop", "1", "-t", fmt(spec.endcard_secs), "-i", str(spec.endcard_logo)]
    cmd += ["-filter_complex", graph, "-map", vlabel, "-map", alabel,
            "-r", str(spec.fps), "-c:v", "libx264", "-profile:v", "high"]
    if spec.quality == "bitrate":
        cmd += ["-preset", "slow", "-b:v", "20M", "-maxrate", "20M", "-bufsize", "40M"]
    elif spec.quality == "crf":
        cmd += ["-preset", "medium", "-crf", "18"]
    else:  # "best": near-transparent, so platform re-encoding starts from a clean source
        cmd += ["-preset", "slow", "-crf", "14"]
    cmd += ["-g", str(spec.fps * 2), "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-color_range", "tv", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(out_path)]
    return cmd


def build_proxy_cmd(src: str, dst: str, ffmpeg: str = "ffmpeg") -> list[str]:
    """Small 540p H.264/AAC file used only for browser preview."""
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-nostdin", "-i", str(src),
            "-vf", "scale=-2:540,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "28", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", str(dst)]


def build_thumbnail_cmd(src: str, t: float, dst: str, width: int = 320,
                        ffmpeg: str = "ffmpeg") -> list[str]:
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
            "-ss", fmt(max(0.0, t)), "-i", str(src), "-frames:v", "1",
            "-vf", f"scale={width}:-2", "-q:v", "4", str(dst)]


def build_audio_pcm_cmd(src: str, sample_rate: int = 8000, ffmpeg: str = "ffmpeg") -> list[str]:
    """Decode to mono signed-16 PCM on stdout (for peak detection)."""
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(src),
            "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-"]


def build_contact_sheet_cmd(video: str, dst: str, duration: float, frames: int = 8,
                            thumb_width: int = 360, ffmpeg: str = "ffmpeg") -> list[str]:
    """One JPG with 6-8 evenly spaced frames (privacy check before posting)."""
    frames = max(6, min(8, int(frames)))
    cols = 4 if frames > 6 else 3
    rows = -(-frames // cols)
    step = duration / frames
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
            "-ss", fmt(step / 2), "-i", str(video),
            "-vf", f"fps=1/{fmt(step)},scale={thumb_width}:-2,"
                   f"tile={cols}x{rows}:padding=6:margin=6:color=black",
            "-frames:v", "1", "-q:v", "3", str(dst)]
