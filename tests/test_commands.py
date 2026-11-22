import pytest

from dailyclip import commands as c
from dailyclip.util import ValidationError


def spec(**kw):
    base = dict(src="in.mp4", start=10, end=30)
    base.update(kw)
    return c.ExportSpec(**base)


def graph(**kw):
    return c.build_filter_graph(spec(font="/f/Poppins-Bold.ttf", **kw))[0]


# ---- filtergraph: blurred template ----------------------------------------
def test_blurred_background_filters():
    g = graph()
    assert "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" in g
    assert "boxblur=30:5" in g
    assert "eq=brightness=-0.15" in g
    assert "noise=" not in g  # grain off by default


def test_grain_strength():
    assert "noise=alls=12:allf=t+u" in graph(grain=12)


def test_foreground_no_zoom_no_crop():
    g = graph(zoom=1.0)
    assert "[fgin]scale=1080:-2[fg]" in g


def test_foreground_zoom_crops_sides():
    g = graph(zoom=1.5)
    assert ("[fgin]scale=1620:-2,crop=1080:trunc(ih*1080/iw/2)*2:"
            "x=(iw-ow)*0.5000:y=(ih-oh)*0.5000[fg]") in g


def test_foreground_centered_overlay_and_fps():
    g = graph()
    assert "overlay=(W-w)/2:min(max(0\\,(H-h)/2+(0))\\,H-h)" in g
    assert "fps=30" in g


def test_vertical_offset_moves_foreground():
    g = graph(fg_y=-300)
    assert "(H-h)/2+(-300)" in g and "min(max(0" in g


def test_pan_left_and_right_when_zoomed():
    assert "x=(iw-ow)*0.0000" in graph(zoom=1.5, pan=-1)
    assert "x=(iw-ow)*1.0000" in graph(zoom=1.5, pan=1)
    assert "x=(iw-ow)*0.7500" in graph(zoom=1.5, pan=0.5)


def test_vertical_pan_when_zoomed():
    assert "y=(ih-oh)*0.0000" in graph(zoom=1.5, pan_y=-1)
    assert "y=(ih-oh)*1.0000" in graph(zoom=1.5, pan_y=1)


def test_zoom_keeps_landscape_window():
    # crop height is derived from the width ratio, so the window never becomes taller
    assert "crop=1080:trunc(ih*1080/iw/2)*2" in graph(zoom=2.0 if False else 1.5)


def test_pan_ignored_without_zoom():
    fg_chain = graph(zoom=1.0, pan=1).split("[fgin]")[-1].split("[fg]")[0]
    assert fg_chain == "scale=1080:-2"


def test_position_validation():
    s = c.spec_from_dict(d(fg_y=-200, pan=0.3, pan_y=-0.5))
    assert s.fg_y == -200 and s.pan == 0.3 and s.pan_y == -0.5
    with pytest.raises(ValidationError):
        c.spec_from_dict(d(pan_y=-3))
    with pytest.raises(ValidationError):
        c.spec_from_dict(d(fg_y=5000))
    with pytest.raises(ValidationError):
        c.spec_from_dict(d(pan=2))


# ---- audio ------------------------------------------------------------------
def test_default_volume_is_20_percent():
    assert "volume=0.200" in graph()


def test_volume_slider_value():
    assert "volume=0.750" in graph(volume=0.75)


def test_mute_uses_silence_not_source_audio():
    g = graph(mute=True)
    assert "anullsrc" in g and "[0:a:0]" not in g


def test_no_source_audio_uses_silence():
    g = graph(has_audio=False)
    assert "anullsrc" in g and "[0:a:0]" not in g


def test_background_copy_has_no_audio():
    # only one audio path ever reads the input
    assert graph().count("[0:a:0]") == 1


# ---- freeze -----------------------------------------------------------------
def test_freeze_pads_video_and_audio():
    g = graph(freeze=1.5)
    assert "tpad=stop_mode=clone:stop_duration=1.5" in g
    assert "apad=whole_dur=21.5" in g


def test_no_freeze_no_tpad():
    assert "tpad" not in graph()


# ---- end card ---------------------------------------------------------------
def test_endcard_navy_logo_concat():
    s = spec(font="/f.ttf", endcard_logo="logo.png")
    g, v, a = c.build_filter_graph(s)
    assert "color=c=0x1E1B4B:s=1080x1920:r=30:d=2.5" in g
    assert "concat=n=2:v=1:a=1[vout][aout]" in g
    assert (v, a) == ("[vout]", "[aout]")
    cmd = c.build_export_cmd(s, "o.mp4")
    assert cmd.count("-i") == 2 and "logo.png" in cmd


def test_total_duration_includes_freeze_and_endcard():
    s = spec(freeze=2, endcard_logo="x.png")
    assert s.total_duration == pytest.approx(20 + 2 + 2.5)


# ---- drawtext ---------------------------------------------------------------
def test_text_requires_textfile():
    t = c.TextOverlay(text="Hi")
    with pytest.raises(ValueError):
        c.drawtext_filters([t], "/f.ttf")


def test_drawtext_uses_textfile_never_inline_text(tmp_path):
    t = c.write_text_files([c.TextOverlay(text="Clutch: 1v3 at 100%", start=1, end=4)], tmp_path)
    f = c.drawtext_filters(t, "/f/Poppins-Bold.ttf")[0]
    assert "textfile=" in f and "Clutch" not in f and "text='" not in f
    assert "expansion=none" in f
    assert (tmp_path / "text_0_0.txt").read_text(encoding="utf-8") == "Clutch: 1v3 at 100%"


def test_drawtext_style(tmp_path):
    t = c.write_text_files([c.TextOverlay(text="HI", start=1, end=4, size=80,
                                          color="#FF5A5F")], tmp_path)
    f = c.drawtext_filters(t, "/f.ttf")[0]
    assert "fontsize=80" in f and "fontcolor=0xFF5A5F" in f
    assert "bordercolor=black" in f and "borderw=7" in f
    assert "x=(w-text_w)/2" in f and "y=250" in f      # centered, y~250 default
    assert "enable='between(t,1,4)'" in f


def test_left_label_position(tmp_path):
    t = c.write_text_files([c.TextOverlay(text="DAY 1", x=60, y=170, size=40,
                                          color="#FF5A5F")], tmp_path)
    f = c.drawtext_filters(t, "/f.ttf")[0]
    assert "x=60:y=170" in f


def test_multiline_becomes_separate_centered_drawtexts(tmp_path):
    t = c.write_text_files([c.TextOverlay(text="ONE\nTWO", size=60)], tmp_path)
    fs = c.drawtext_filters(t, "/f.ttf")
    assert len(fs) == 2 and "y=250" in fs[0] and f"y={250 + c.line_height(60)}" in fs[1]


def test_text_with_unicode_and_quotes_in_file(tmp_path):
    t = c.write_text_files([c.TextOverlay(text="It's \"wild\" 🔥 café")], tmp_path)
    assert (tmp_path / "text_0_0.txt").read_text(encoding="utf-8") == "It's \"wild\" 🔥 café"


# ---- Windows path escaping ------------------------------------------------
def test_escape_windows_drive_colon_and_backslashes():
    assert c.escape_filter_path(r"C:\Users\Me\My Clips\Poppins-Bold.ttf") == \
        r"'C\:/Users/Me/My Clips/Poppins-Bold.ttf'"


def test_escape_plain_posix():
    assert c.escape_filter_path("/a b/c.ttf") == "'/a b/c.ttf'"


def test_fontfile_escaped_in_filter(tmp_path):
    t = c.write_text_files([c.TextOverlay(text="x")], tmp_path)
    f = c.drawtext_filters(t, r"C:\Users\Me\clip editor\static\fonts\Poppins-Bold.ttf")[0]
    assert r"fontfile='C\:/Users/Me/clip editor/static/fonts/Poppins-Bold.ttf'" in f


# ---- full command -----------------------------------------------------------
def test_export_command_encoding_flags():
    cmd = c.build_export_cmd(spec(font="/f.ttf"), "out.mp4")
    j = " ".join(cmd)
    for needle in ("-c:v libx264", "-crf 18", "-pix_fmt yuv420p", "-c:a aac", "-b:a 192k",
                   "-movflags +faststart", "-r 30"):
        assert needle in j
    assert cmd[-1] == "out.mp4"
    assert "-ss 10 -t 20 -i in.mp4" in j


def test_export_command_bitrate_mode():
    j = " ".join(c.build_export_cmd(spec(font="/f.ttf", quality="bitrate"), "o.mp4"))
    assert "-b:v 20M" in j and "-crf" not in j


def test_paths_with_spaces_stay_single_arguments():
    cmd = c.build_export_cmd(spec(src=r"C:\My Videos\PS5 clip.mp4", font="/f.ttf"),
                             r"C:\Out Dir\a b.mp4")
    assert r"C:\My Videos\PS5 clip.mp4" in cmd and r"C:\Out Dir\a b.mp4" in cmd


def test_no_watermark_filters():
    g = graph()
    assert "movie=" not in g and "watermark" not in g.lower()


def test_proxy_command_540p():
    j = " ".join(c.build_proxy_cmd("a.mkv", "p.mp4"))
    assert "scale=-2:540" in j and "libx264" in j


def test_thumbnail_command():
    cmd = c.build_thumbnail_cmd("a.mp4", 12.5, "t.jpg")
    assert cmd[cmd.index("-ss") + 1] == "12.5" and "-frames:v" in cmd


def test_contact_sheet_frame_count_clamped():
    assert "tile=3x2" in " ".join(c.build_contact_sheet_cmd("a.mp4", "s.jpg", 60, 3))
    assert "tile=4x2" in " ".join(c.build_contact_sheet_cmd("a.mp4", "s.jpg", 60, 99))


# ---- validation -------------------------------------------------------------
def d(**kw):
    base = dict(src="in.mp4", start=5, end=20)
    base.update(kw)
    return base


def test_end_before_start_is_rejected():
    with pytest.raises(ValidationError, match="must be after start"):
        c.spec_from_dict(d(start=20, end=5))


def test_end_equal_start_is_rejected():
    with pytest.raises(ValidationError):
        c.spec_from_dict(d(start=5, end=5))


def test_end_past_video_rejected():
    with pytest.raises(ValidationError, match="past the end"):
        c.spec_from_dict(d(end=500), src_duration=100)


def test_zoom_range():
    with pytest.raises(ValidationError):
        c.spec_from_dict(d(zoom=2))
    with pytest.raises(ValidationError):
        c.spec_from_dict(d(zoom=0.5))
    assert c.spec_from_dict(d(zoom=1.5)).zoom == 1.5


def test_freeze_max_two_seconds():
    with pytest.raises(ValidationError):
        c.spec_from_dict(d(freeze=3))


def test_text_end_before_start_rejected():
    with pytest.raises(ValidationError, match="Text line 1"):
        c.spec_from_dict(d(texts=[{"text": "hi", "start": 5, "end": 2}]))


def test_text_defaults_and_red_color():
    s = c.spec_from_dict(d(texts=[{"text": "hi", "color": "red"}, {"text": "  "}]))
    assert len(s.texts) == 1
    assert s.texts[0].color == "#FF5A5F" and s.texts[0].end == 15 and s.texts[0].y == 250


def test_bad_number():
    with pytest.raises(ValidationError):
        c.spec_from_dict(d(start="abc"))


def test_missing_logo_rejected():
    with pytest.raises(ValidationError, match="logo not found"):
        c.spec_from_dict(d(endcard_logo="/nope/logo.png"))
