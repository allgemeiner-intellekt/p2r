from pathlib import Path


def test_rewrite_markdown_image_links_replaces_local_paths(tmp_path: Path):
    from p2r.image_upload import rewrite_markdown_image_links

    out = tmp_path / "out"
    out.mkdir()
    (out / "images").mkdir()
    img = out / "images" / "a.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    md = "x\n\n![](images/a.png)\n"
    rewritten = rewrite_markdown_image_links(md, out, lambda p: "https://img.example/a.png")
    assert "https://img.example/a.png" in rewritten


def test_rewrite_markdown_image_links_keeps_remote_urls(tmp_path: Path):
    from p2r.image_upload import rewrite_markdown_image_links

    out = tmp_path / "out"
    out.mkdir()

    md = "x\n\n![](https://example.com/a.png)\n"
    rewritten = rewrite_markdown_image_links(md, out, lambda p: "https://img.example/should-not-happen.png")
    assert rewritten == md


def test_collect_local_images_from_markdown_dedupes_and_filters(tmp_path: Path):
    from p2r.image_upload import collect_local_images_from_markdown

    out = tmp_path / "out"
    out.mkdir()
    (out / "images").mkdir()
    a = out / "images" / "a.png"
    b = out / "images" / "b.jpg"
    a.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    b.write_bytes(b"\xff\xd8\xff fake")

    md = out / "full.md"
    md.write_text(
        "\n".join(
            [
                "![](images/a.png)",
                "![](images/a.png)",  # dup
                "![](images/b.jpg \"t\")",
                "![](https://example.com/remote.png)",
                "![](images/missing.png)",
                "<img src=\"images/a.png\" />",
            ]
        ),
        encoding="utf-8",
    )

    found = collect_local_images_from_markdown(out)
    assert found == sorted({a.resolve(), b.resolve()})


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_picgo_server_uploader_raises_on_failure(monkeypatch, tmp_path: Path):
    from p2r.image_upload import PicGoServerUploader, PicGoServerUploaderConfig, ImageUploadError

    def fake_post(url, json=None, headers=None, timeout=None, files=None):  # noqa: A002
        return _FakeResponse(200, {"success": False, "message": "boom"})

    monkeypatch.setattr("p2r.image_upload.requests.post", fake_post)

    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    u = PicGoServerUploader(PicGoServerUploaderConfig(url="http://x/upload"))
    try:
        u.upload(img)
        assert False, "expected ImageUploadError"
    except ImageUploadError as e:
        assert "boom" in str(e)


def test_picgo_server_uploader_extracts_url(monkeypatch, tmp_path: Path):
    from p2r.image_upload import PicGoServerUploader, PicGoServerUploaderConfig

    def fake_post(url, json=None, headers=None, timeout=None, files=None):  # noqa: A002
        return _FakeResponse(200, {"success": True, "result": ["https://img.example/a.png"]})

    monkeypatch.setattr("p2r.image_upload.requests.post", fake_post)

    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    u = PicGoServerUploader(PicGoServerUploaderConfig(url="http://x/upload"))
    assert u.upload(img) == "https://img.example/a.png"
