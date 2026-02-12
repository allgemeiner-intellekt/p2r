import json
from pathlib import Path


def test_load_config_creates_v2_default(monkeypatch, tmp_path: Path):
    from p2r import config as cfg

    path = tmp_path / "c.json"
    monkeypatch.setenv(cfg.ENV_CONFIG_PATH_KEY, str(path))

    loaded = cfg.load_config()
    assert loaded["version"] == cfg.CONFIG_VERSION
    assert loaded["default_profile"] == "default"
    assert "default" in loaded["profiles"]
    assert loaded["image_upload"]["mode"] == "picgo_server"
    assert (path).exists()

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["version"] == cfg.CONFIG_VERSION
    assert "profiles" in on_disk


def test_load_config_migrates_v1_to_v2(monkeypatch, tmp_path: Path):
    from p2r import config as cfg

    path = tmp_path / "v1.json"
    monkeypatch.setenv(cfg.ENV_CONFIG_PATH_KEY, str(path))

    v1 = {
        "mineru": {
            "api_token": "t",
            "api_base_url": "https://mineru.net/api/v4",
            "poll_interval": 9,
            "max_poll_time": 123,
        },
        "output": {"temp_dir": "/tmp/custom"},
        "image_upload": {"enabled": True, "mode": "command", "command": "picgo upload \"{file}\""},
    }
    path.write_text(json.dumps(v1), encoding="utf-8")

    loaded = cfg.load_config()
    assert loaded["version"] == cfg.CONFIG_VERSION
    assert loaded["default_profile"] == "default"
    assert "default" in loaded["profiles"]
    assert loaded["output"]["temp_dir"] == "/tmp/custom"
    assert loaded["mineru"]["poll_interval"] == 9
    assert loaded["image_upload"]["enabled"] is True

    # Best-effort writeback: migrated config should now be v2 on disk.
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["version"] == cfg.CONFIG_VERSION
    assert "profiles" in on_disk
    assert "default_profile" in on_disk
