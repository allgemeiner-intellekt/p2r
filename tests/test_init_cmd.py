import json
from pathlib import Path


def test_init_creates_config_and_profile(monkeypatch, tmp_path: Path):
    from click.testing import CliRunner
    import p2r.cli as cli
    from p2r import config as cfg

    config_path = tmp_path / "config.json"
    monkeypatch.setenv(cfg.ENV_CONFIG_PATH_KEY, str(config_path))

    runner = CliRunner()
    user_input = "\n".join(
        [
            "TOKEN123",  # token
            "",  # create profile? (default: yes)
            "reading",  # profile name
            "./md",  # markdown dir
            "./html",  # html dir
            "",
        ]
    )
    r = runner.invoke(cli.cli, ["init"], input=user_input)
    assert r.exit_code == 0
    assert config_path.exists()

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["mineru"]["api_token"] == "TOKEN123"
    assert data["default_profile"] == "reading"
    assert "reading" in data["profiles"]
    assert data["profiles"]["reading"]["export"]["markdown_dir"] == "./md"


def test_init_refuses_overwrite_without_force(monkeypatch, tmp_path: Path):
    from click.testing import CliRunner
    import p2r.cli as cli
    from p2r import config as cfg

    config_path = tmp_path / "config.json"
    monkeypatch.setenv(cfg.ENV_CONFIG_PATH_KEY, str(config_path))
    config_path.write_text("{}", encoding="utf-8")

    runner = CliRunner()
    r = runner.invoke(cli.cli, ["init"])
    assert r.exit_code != 0


def test_init_can_skip_profile_creation(monkeypatch, tmp_path: Path):
    from click.testing import CliRunner
    import p2r.cli as cli
    from p2r import config as cfg

    config_path = tmp_path / "config.json"
    monkeypatch.setenv(cfg.ENV_CONFIG_PATH_KEY, str(config_path))

    runner = CliRunner()
    user_input = "\n".join(
        [
            "TOKEN123",  # token
            "n",  # create profile? -> no
            "",
        ]
    )
    r = runner.invoke(cli.cli, ["init"], input=user_input)
    assert r.exit_code == 0
    assert config_path.exists()

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["mineru"]["api_token"] == "TOKEN123"
    assert data["default_profile"] == "default"
    assert "default" in data["profiles"]
    assert "reading" not in data["profiles"]
