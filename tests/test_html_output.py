import json
from pathlib import Path

import pytest


class _FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_request_upload_urls_includes_extra_formats(monkeypatch, tmp_path: Path):
    from p2r.mineru import MinerUClient

    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: A002
        seen["url"] = url
        seen["json"] = json
        return _FakeResponse(
            {"code": 0, "data": {"batch_id": "b", "file_urls": ["https://upload"]}}
        )

    monkeypatch.setattr("p2r.mineru.requests.post", fake_post)

    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    c = MinerUClient(api_token="t", api_base_url="https://mineru.net/api/v4")
    c.request_upload_urls(pdf, model_version="vlm", extra_formats=["html"])

    assert seen["json"]["model_version"] == "vlm"
    assert seen["json"]["extra_formats"] == ["html"]


def test_cli_html_default_and_no_html(monkeypatch, tmp_path: Path):
    from click.testing import CliRunner
    import p2r.cli as cli

    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    calls = []

    class FakeClient:
        def parse_pdf(self, pdf_file, output_dir, model_version="vlm", extra_formats=None):
            calls.append(
                {
                    "pdf_file": pdf_file,
                    "output_dir": output_dir,
                    "model_version": model_version,
                    "extra_formats": extra_formats,
                }
            )
            yield {"state": "completed", "output_dir": str(output_dir)}

    monkeypatch.setattr(cli, "MinerUClient", lambda: FakeClient())
    monkeypatch.setattr(cli, "get_api_token", lambda: "t")

    out = tmp_path / "out"
    runner = CliRunner()

    # Default: HTML enabled => extra_formats includes ["html"]
    r1 = runner.invoke(cli.main, ["convert", str(pdf), "-o", str(out)])
    assert r1.exit_code == 0
    assert calls[-1]["extra_formats"] == ["html"]

    # Explicit: --no-html => extra_formats is None
    r2 = runner.invoke(cli.main, ["convert", str(pdf), "-o", str(out), "--no-html"])
    assert r2.exit_code == 0
    assert calls[-1]["extra_formats"] is None


def test_organize_output_dir_moves_raw_artifacts(tmp_path: Path):
    from p2r.mineru import MinerUClient

    out = tmp_path / "out"
    out.mkdir()
    (out / "images").mkdir()
    (out / "full.md").write_text("# x", encoding="utf-8")
    (out / "layout.json").write_text("{}", encoding="utf-8")
    (out / "id_content_list.json").write_text("[]", encoding="utf-8")
    (out / "id_model.json").write_text("[]", encoding="utf-8")
    (out / "id_origin.pdf").write_bytes(b"%PDF-1.4 fake")

    c = MinerUClient(api_token="t", api_base_url="https://mineru.net/api/v4")
    c._organize_output_dir(out)

    assert (out / "full.md").exists()
    assert (out / "images").exists()
    assert (out / "raw" / "layout.json").exists()
    assert (out / "raw" / "id_content_list.json").exists()
    assert (out / "raw" / "id_model.json").exists()
    assert (out / "raw" / "id_origin.pdf").exists()

