import importlib
import subprocess

import pytest

from conftest import needs_ffmpeg


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DAILYCLIP_DATA", str(tmp_path / "data"))
    import app as app_module
    importlib.reload(app_module)
    app_module.STATE.update(video=None, proxy=None)
    app_module.app.testing = True
    return app_module.app.test_client(), app_module


def test_index_and_status(client):
    c, _ = client
    assert c.get("/").status_code == 200
    assert "ok" in c.get("/api/status").get_json()


def test_load_missing_file(client):
    c, _ = client
    r = c.post("/api/load", json={"path": "/definitely/not/here.mp4"})
    assert r.status_code in (400, 500)
    assert "not found" in r.get_json()["error"].lower() or "ffmpeg" in r.get_json()["error"].lower()


@needs_ffmpeg
def test_load_bad_file(client, tmp_path):
    c, _ = client
    bad = tmp_path / "bad.mp4"
    bad.write_text("this is not a video")
    r = c.post("/api/load", json={"path": str(bad)})
    assert r.status_code == 400 and r.get_json()["code"] == "bad_file"


def test_export_without_video(client):
    c, _ = client
    r = c.post("/api/export", json={"start": 1, "end": 5})
    assert r.status_code == 400 and "Load a video" in r.get_json()["error"]


@needs_ffmpeg
def test_export_end_before_start_message(client, tmp_path):
    c, _ = client
    src = tmp_path / "a b.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc=size=320x180:rate=10:duration=3", "-pix_fmt", "yuv420p", str(src)],
                   check=True)
    assert c.post("/api/load", json={"path": f'"{src}"'}).status_code == 200  # quoted path ok
    r = c.post("/api/export", json={"start": 5, "end": 2})
    assert r.status_code == 400
    assert "must be after start" in r.get_json()["error"]


def test_presets_roundtrip(client):
    c, _ = client
    assert "DAY 1 label" in c.get("/api/presets").get_json()
    r = c.post("/api/presets", json={"name": "mine", "style": {"size": 55, "color": "red", "y": 300}})
    assert r.get_json()["mine"]["size"] == 55
    assert "mine" not in c.delete("/api/presets/mine").get_json()


def test_unknown_route_is_json(client):
    c, _ = client
    r = c.get("/api/nope")
    assert r.status_code == 404 and r.get_json()["error"]
