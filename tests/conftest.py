import sys
from pathlib import Path

import pytest


# Allow running tests without installing the package (src-layout).
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _isolate_config_path(monkeypatch, tmp_path_factory):
    """Prevent tests from reading/writing the user's real ~/.p2r_config.json."""
    cfg_dir = tmp_path_factory.mktemp("p2r_cfg")
    monkeypatch.setenv("P2R_CONFIG_PATH", str(cfg_dir / "config.json"))
