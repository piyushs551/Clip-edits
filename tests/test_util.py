from datetime import date

from dailyclip import util


def test_slugify():
    assert util.slugify("Clutch 1v3 — Warzone!!") == "clutch-1v3-warzone"
    assert util.slugify("") == "short"
    assert util.slugify("***") == "short"


def test_output_name():
    assert util.output_name("My Clip", date(2026, 11, 22)) == "2026-11-22_my-clip.mp4"


def test_unique_path(tmp_path):
    p = tmp_path / "a.mp4"
    assert util.unique_path(p) == p
    p.write_text("x")
    assert util.unique_path(p).name == "a-2.mp4"


def test_clean_user_path():
    assert util.clean_user_path('  "C:\\a b\\c.mp4" ') == "C:\\a b\\c.mp4"


def test_ffmpeg_missing_message(monkeypatch):
    monkeypatch.setattr(util.shutil, "which", lambda n: None)
    st = util.ffmpeg_status()
    assert not st["ok"] and "winget install Gyan.FFmpeg" in st["message"]
    try:
        util.require_ffmpeg()
    except util.FFmpegMissing as e:
        assert "winget install Gyan.FFmpeg" in str(e)
    else:
        raise AssertionError("should raise")
