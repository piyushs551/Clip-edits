"""Integration: synthetic 10 s clip -> real export through ffmpeg."""
import json
import subprocess
from pathlib import Path

import pytest

from conftest import needs_ffmpeg
from dailyclip import commands as c
from dailyclip import peaks
from dailyclip.probe import probe
from dailyclip.runner import run_simple, run_with_progress
from dailyclip.util import find_font

pytestmark = needs_ffmpeg


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    d = tmp_path_factory.mktemp("synthetic dir")  # space in path on purpose
    out = d / "synthetic clip.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=10",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)],
        check=True)
    return out


@pytest.fixture(scope="module")
def logo(tmp_path_factory):
    out = tmp_path_factory.mktemp("logo") / "logo.png"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=orange:s=400x200", "-frames:v", "1", str(out)], check=True)
    return out


def streams(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                          "-show_format", str(path)], capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    a = next(s for s in data["streams"] if s["codec_type"] == "audio")
    return v, a, float(data["format"]["duration"])


def test_probe_synthetic_clip(clip):
    info = probe(str(clip))
    assert (info["width"], info["height"], info["fps"]) == (1280, 720, 30.0)
    assert info["vcodec"] == "h264" and info["has_audio"] and info["browser_playable"]
    assert 9.9 < info["duration"] < 10.2


def test_full_export_with_text_grain_zoom_freeze_endcard(clip, logo, tmp_path):
    spec = c.ExportSpec(src=str(clip), start=2, end=8, zoom=1.25, volume=0.2, grain=10,
                        freeze=1.0, endcard_logo=str(logo), has_audio=True,
                        texts=[c.TextOverlay(text="Clutch: 1v3 at 100%", start=0, end=3),
                               c.TextOverlay(text="DAY 1", x=60, y=170, size=40,
                                             color="#FF5A5F", start=0, end=6)])
    spec.texts = c.write_text_files(spec.texts, tmp_path / "texts dir")
    out = tmp_path / "out dir" / "short.mp4"
    out.parent.mkdir()
    progress = []
    run_with_progress(c.build_export_cmd(spec, str(out)), spec.total_duration, progress.append)

    v, a, dur = streams(out)
    assert (v["width"], v["height"]) == (1080, 1920)
    assert v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p"
    assert v["r_frame_rate"] == "30/1"
    assert a["codec_name"] == "aac"
    assert abs(dur - (6 + 1 + 2.5)) < 0.3          # clip + freeze + end card
    assert progress and progress[-1] == 1.0
    # faststart: moov atom precedes mdat
    head = out.read_bytes()[:4096 * 64]
    assert head.find(b"moov") != -1 and head.find(b"moov") < head.find(b"mdat")

    sheet = tmp_path / "sheet.jpg"
    run_simple(c.build_contact_sheet_cmd(str(out), str(sheet), dur, 8))
    assert sheet.stat().st_size > 5000


def test_export_mute_and_bitrate_mode(clip, tmp_path):
    spec = c.ExportSpec(src=str(clip), start=0, end=4, mute=True, quality="bitrate")
    out = tmp_path / "m.mp4"
    run_simple(c.build_export_cmd(spec, str(out)))
    v, a, dur = streams(out)
    assert (v["width"], v["height"]) == (1080, 1920) and abs(dur - 4) < 0.3
    vol = subprocess.run(["ffmpeg", "-i", str(out), "-af", "volumedetect", "-vn", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    assert "max_volume: -91" in vol or "max_volume: -inf" in vol   # silent


def test_game_volume_applies(clip, tmp_path):
    def peak(volume):
        out = tmp_path / f"v{volume}.mp4"
        run_simple(c.build_export_cmd(c.ExportSpec(src=str(clip), start=0, end=3, volume=volume),
                                      str(out)))
        err = subprocess.run(["ffmpeg", "-i", str(out), "-af", "volumedetect", "-vn", "-f",
                              "null", "-"], capture_output=True, text=True).stderr
        return float(err.split("max_volume:")[1].split("dB")[0])
    assert peak(1.0) - peak(0.2) > 10   # ~14 dB quieter


def test_drawtext_with_colon_and_space_in_font_path(clip, tmp_path):
    """Regression for the Windows 'C:' fontfile problem (colon + spaces in path)."""
    odd = tmp_path / "my folder:with colon"
    odd.mkdir()
    font = odd / "Bold Font.ttf"
    font.write_bytes(Path(find_font()).read_bytes())
    spec = c.ExportSpec(src=str(clip), start=0, end=2, font=str(font),
                        texts=[c.TextOverlay(text="a: b % c")])
    spec.texts = c.write_text_files(spec.texts, tmp_path / "t")
    run_simple(c.build_export_cmd(spec, str(tmp_path / "o.mp4")))
    assert (tmp_path / "o.mp4").stat().st_size > 1000


def test_suggest_moments_finds_loud_bursts(tmp_path):
    src = tmp_path / "burst.mp4"
    # quiet noise floor with loud bursts at ~10 s and ~30 s of a 45 s file
    expr = "0.02*sin(2*PI*220*t)+0.9*sin(2*PI*880*t)*(between(t,10,10.4)+between(t,30,30.4))"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=320x180:r=10:d=45", "-f", "lavfi", "-i",
                    f"aevalsrc='{expr}':s=44100:d=45", "-c:v", "libx264", "-c:a", "aac",
                    "-shortest", str(src)], check=True)
    found = peaks.suggest_moments(str(src), max_peaks=10)
    times = [p["time"] for p in found]
    assert any(9.9 <= t <= 10.5 for t in times) and any(29.9 <= t <= 30.5 for t in times)
    assert all(b - a >= 4 for a, b in zip(times, times[1:]))


@pytest.fixture(scope="module")
def noisy(tmp_path_factory):
    """Detail everywhere (random noise): blurs to flat grey in the background, stays
    busy in the sharp foreground, so the foreground's rows are easy to locate."""
    out = tmp_path_factory.mktemp("noisy") / "noisy.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=gray:s=1280x720:r=30:d=3,noise=alls=70:allf=t", "-f", "lavfi", "-i",
                    "sine=frequency=300:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "10", "-c:a", "aac", "-shortest", str(out)], check=True)
    return out


def _frame(path, vf="format=gray"):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-vf", vf,
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8)


def _energy(path):
    import numpy as np
    img = _frame(path).reshape(1920, 1080).astype(float)
    return np.abs(np.diff(img, axis=1)).mean(axis=1)      # detail per row


def _sharp_rows(path):
    """(top, bottom) rows of the sharp foreground (the busy rows)."""
    import numpy as np
    e = _energy(path)
    rows = np.flatnonzero(e > 0.5 * e.max())
    return int(rows.min()), int(rows.max())


def test_vertical_position_moves_clip_and_is_clamped(noisy, tmp_path):
    tops = {}
    for name, fg_y in (("mid", 0), ("up", -300), ("down", 300), ("way_up", -960), ("way_down", 960)):
        out = tmp_path / f"{name}.mp4"
        run_simple(c.build_export_cmd(c.ExportSpec(src=str(noisy), start=0.5, end=1.5, fg_y=fg_y),
                                      str(out)))
        tops[name] = _sharp_rows(out)
    # 1280x720 -> 1080x607 window, centered top = 656
    assert abs(tops["mid"][0] - 656) < 15 and abs(tops["mid"][1] - 1263) < 15
    assert abs(tops["up"][0] - 356) < 15 and abs(tops["down"][0] - 956) < 15
    assert tops["way_up"][0] < 15                    # clamped to the top edge
    assert tops["way_down"][1] > 1905                # clamped to the bottom edge


def test_zoom_keeps_landscape_window_and_magnifies(noisy, clip, tmp_path):
    import numpy as np
    def run(zoom):
        out = tmp_path / f"z{zoom}.mp4"
        run_simple(c.build_export_cmd(c.ExportSpec(src=str(noisy), start=0.5, end=1.5, zoom=zoom),
                                      str(out)))
        return out
    base, zoomed = run(1.0), run(1.5)
    tb, bb = _sharp_rows(base); tz, bz = _sharp_rows(zoomed)
    # the window is the same size and place (still full landscape, not taller)
    assert abs(tb - tz) < 15 and abs(bb - bz) < 15
    # ...but the picture inside it is magnified: same window, different (zoomed) content
    def win(zoom):
        out = tmp_path / f"w{zoom}.mp4"
        run_simple(c.build_export_cmd(c.ExportSpec(src=str(clip), start=1, end=2, zoom=zoom),
                                      str(out)))
        return _frame(out).reshape(1920, 1080)[700:1200].astype(float)
    assert np.abs(win(1.0) - win(1.5)).mean() > 5


def test_pan_shows_different_part_of_frame(clip, tmp_path):
    import numpy as np
    def window(pan, pan_y):
        out = tmp_path / f"pan{pan}_{pan_y}.mp4"
        run_simple(c.build_export_cmd(c.ExportSpec(src=str(clip), start=1, end=2, zoom=1.5,
                                                   pan=pan, pan_y=pan_y), str(out)))
        return _frame(out).reshape(1920, 1080)[700:1200].astype(float)
    left, right, top, bottom = window(-1, 0), window(1, 0), window(0, -1), window(0, 1)
    assert np.abs(left - right).mean() > 3
    assert np.abs(top - bottom).mean() > 3


def test_best_quality_is_tagged_bt709_and_larger_than_good(clip, tmp_path):
    sizes = {}
    for q in ("best", "crf"):
        out = tmp_path / f"{q}.mp4"
        run_simple(c.build_export_cmd(c.ExportSpec(src=str(clip), start=1, end=4, quality=q),
                                      str(out)))
        sizes[q] = out.stat().st_size
    v, _, _ = streams(out)
    assert v["profile"] == "High" and v["color_space"] == "bt709"
    assert v["color_transfer"] == "bt709" and v["color_primaries"] == "bt709"
    assert sizes["best"] > sizes["crf"] * 1.15      # CRF 14 spends clearly more bits than 18


def test_60fps_export(clip, tmp_path):
    out = tmp_path / "f60.mp4"
    run_simple(c.build_export_cmd(c.ExportSpec(src=str(clip), start=1, end=3, fps=60,
                                               quality="crf"), str(out)))
    v, _, dur = streams(out)
    assert v["r_frame_rate"] == "60/1" and abs(dur - 2) < 0.3
