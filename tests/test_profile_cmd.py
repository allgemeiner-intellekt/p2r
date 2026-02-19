import json
from pathlib import Path


def test_profile_creates_profile_interactive_no_default_switch(monkeypatch, tmp_path: Path):
    from click.testing import CliRunner
    import p2r.cli as cli
    from p2r import config as cfg

    config_path = tmp_path / "config.json"
    monkeypatch.setenv(cfg.ENV_CONFIG_PATH_KEY, str(config_path))

    runner = CliRunner()
    user_input = "\n".join(
        [
            "reading",  # profile name
            "./md",  # markdown dir
            "./html",  # html dir
            "",  # set default? (default: no)
            "",
        ]
    )
    r = runner.invoke(cli.cli, ["profile"], input=user_input)
    assert r.exit_code == 0
    assert config_path.exists()

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "reading" in data["profiles"]
    assert data["profiles"]["reading"]["export"]["markdown_dir"] == "./md"
    assert data["profiles"]["reading"]["export"]["html_dir"] == "./html"
    assert data["default_profile"] == "default"


def test_profile_creates_profile_with_set_default_flag(monkeypatch, tmp_path: Path):
    from click.testing import CliRunner
    import p2r.cli as cli
    from p2r import config as cfg

    config_path = tmp_path / "config.json"
    monkeypatch.setenv(cfg.ENV_CONFIG_PATH_KEY, str(config_path))

    runner = CliRunner()
    r = runner.invoke(
        cli.cli,
        ["profile", "--name", "reading", "--md-dir", "./md", "--html-dir", "./html", "--set-default"],
    )
    assert r.exit_code == 0

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "reading" in data["profiles"]
    assert data["default_profile"] == "reading"


def test_profile_flag_name_conflict_fails(monkeypatch, tmp_path: Path):
    from click.testing import CliRunner
    import p2r.cli as cli
    from p2r import config as cfg

    config_path = tmp_path / "config.json"
    monkeypatch.setenv(cfg.ENV_CONFIG_PATH_KEY, str(config_path))

    existing = cfg.get_default_config()
    existing.setdefault("profiles", {})["reading"] = cfg.get_default_profile()
    config_path.write_text(json.dumps(existing), encoding="utf-8")

    runner = CliRunner()
    r = runner.invoke(
        cli.cli,
        ["profile", "--name", "reading", "--md-dir", "./md", "--html-dir", "./html"],
    )
    assert r.exit_code != 0

