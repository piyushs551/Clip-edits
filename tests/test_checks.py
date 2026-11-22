import pytest

from dailyclip import checks as k
from dailyclip import commands as c


def mk(texts=(), start=0, end=20, **kw):
    return c.ExportSpec(src="x.mp4", start=start, end=end, texts=list(texts), **kw)


def T(text="HOOK", **kw):
    return c.TextOverlay(text=text, **kw)


def by_id(results):
    return {r["id"]: r for r in results}


def test_all_good_short_passes():
    spec = mk([T("Wait for it", start=0, end=3), T("Same spot, new result", start=3, end=7),
               T("Follow for more", start=7, end=10)], end=12)
    r = by_id(k.check_short(spec))
    assert {i: v["status"] for i, v in r.items() if i != "privacy"} == {
        "hook": "pass", "words": "pass", "safe_area": "pass", "length": "pass",
        "last_frame": "pass", "pacing": "pass"}
    assert r["privacy"]["status"] == "manual"


def test_no_text_warns_hook():
    r = by_id(k.check_short(mk()))
    assert r["hook"]["status"] == "warn" and "No hook text" in r["hook"]["message"]
    assert "pacing" not in r                      # nothing to pace without text


def test_hook_on_frame_one_vs_late():
    assert k.check_hook(mk([T(start=0)]))["status"] == "pass"
    late = k.check_hook(mk([T(start=2)]))
    assert late["status"] == "warn" and "frame one" in late["message"]
    very_late = k.check_hook(mk([T(start=5)]))
    assert very_late["status"] == "warn" and "first 3 s" in very_late["message"]


def test_label_does_not_count_as_hook():
    day1 = T("DAY 1", x=60, y=170, size=40, color="#FF5A5F", start=0)
    assert k.check_hook(mk([day1]))["status"] == "warn"
    assert k.check_hook(mk([day1, T(start=0)]))["status"] == "pass"


def test_six_words_ok_seven_warns():
    assert k.check_words(mk([T("one two three four five six")]))["status"] == "pass"
    r = k.check_words(mk([T("one two three four five six seven")]))
    assert r["status"] == "warn" and "7 words" in r["message"]


def test_words_checked_per_line():
    two_lines = "one two three four five six\nseven eight nine ten eleven twelve"
    assert k.check_words(mk([T(two_lines)]))["status"] == "pass"


def test_safe_area_top_bottom():
    assert k.check_safe_area(mk([T("HI", y=250)]))["status"] == "pass"
    assert "too high" in k.check_safe_area(mk([T("HI", y=60)]))["message"]
    assert "too low" in k.check_safe_area(mk([T("HI", y=1500)]))["message"]


def test_safe_area_default_label_position_is_fine():
    assert k.check_safe_area(mk([T("DAY 1", x=60, y=170, size=40)]))["status"] == "pass"


def test_safe_area_right_edge_wide_text():
    r = k.check_safe_area(mk([T("THIS IS A VERY LONG LINE OF TEXT", size=72, y=250)]))
    assert r["status"] == "warn" and "right 150px" in r["message"]


def test_safe_area_left_label_pushed_right():
    r = k.check_safe_area(mk([T("LABEL", x=900, size=60, y=250)]))
    assert "right 150px" in r["message"]


def test_safe_area_multiline_bottom():
    r = k.check_safe_area(mk([T("a\nb\nc\nd\ne", size=80, y=1300)]))
    assert "too low" in r["message"]


def test_length_limit():
    assert k.check_length(mk(end=25))["status"] == "pass"
    assert k.check_length(mk(end=30))["status"] == "warn"          # not under 30
    assert k.check_length(mk(end=25, freeze=2, endcard_logo="l.png"))["status"] == "pass"   # 29.5 s
    assert k.check_length(mk(end=26, freeze=2, endcard_logo="l.png"))["status"] == "warn"   # 30.5 s


def test_pacing_warns_on_long_static_stretch():
    r = k.check_pacing(mk([T(start=0, end=6)], end=10))
    assert r["status"] == "warn" and "6.0 s" in r["message"]


def test_last_frame_text_still_showing_warns():
    assert k.check_last_frame(mk([T(start=0, end=None)]))["status"] == "warn"
    assert k.check_last_frame(mk([T(start=0, end=20)], end=20))["status"] == "warn"
    assert k.check_last_frame(mk([T(start=0, end=18)], end=20))["status"] == "pass"


def test_end_card_counts_as_clean_last_frame():
    spec = mk([T(start=0, end=None)], endcard_logo="logo.png")
    assert k.check_last_frame(spec)["status"] == "pass"


def test_persistent_label_is_ok_on_last_frame():
    assert k.check_last_frame(mk([T("DAY 1", x=60, y=170, size=40, end=None)]))["status"] == "pass"


def test_estimate_width_is_close_to_measured_poppins():
    # measured in-browser: 28-char caps+spaces string at 100px = ~1517px
    est = k.estimate_text_width("WAIT FOR THE END OF THE CLIP", 100)
    assert 1450 < est < 1700


def test_export_default_quality_is_20mbps():
    assert c.spec_from_dict({"src": "x", "start": 0, "end": 5}).quality == "bitrate"
    j = " ".join(c.build_export_cmd(c.ExportSpec(src="a", start=0, end=5, font="/f.ttf"), "o.mp4"))
    assert "-b:v 20M" in j and "-maxrate 20M" in j
