"""Image upload + Markdown link rewriting.

This module is intentionally small and dependency-light. It supports:
- command mode: run a local command per image and parse a URL from stdout
- picgo_server mode: upload via an HTTP endpoint compatible with common PicGo server plugins
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Tuple, Set, List

import requests


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff", ".tif"}


class ImageUploadError(RuntimeError):
    pass


def _looks_like_image(p: Path) -> bool:
    return p.suffix.lower() in _IMAGE_EXTS


def _extract_url_from_stdout(stdout: str) -> str:
    s = stdout.strip()
    if not s:
        raise ImageUploadError("Uploader produced empty stdout; cannot extract URL.")

    # Try JSON first (different uploaders use different shapes).
    try:
        payload = json.loads(s)
    except json.JSONDecodeError:
        payload = None

    if payload is not None:
        # Common patterns:
        # - {"url": "..."}
        # - {"imgUrl": "..."}
        # - {"result": ["..."]} or {"result": [{"url": "..."}]}
        if isinstance(payload, dict):
            for k in ("url", "imgUrl", "img_url", "link", "data"):
                v = payload.get(k)
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    return v
            result = payload.get("result")
            if isinstance(result, list) and result:
                first = result[0]
                if isinstance(first, str) and first.startswith(("http://", "https://")):
                    return first
                if isinstance(first, dict):
                    for k in ("url", "imgUrl", "img_url", "link"):
                        v = first.get(k)
                        if isinstance(v, str) and v.startswith(("http://", "https://")):
                            return v

        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, str) and first.startswith(("http://", "https://")):
                return first
            if isinstance(first, dict):
                for k in ("url", "imgUrl", "img_url", "link"):
                    v = first.get(k)
                    if isinstance(v, str) and v.startswith(("http://", "https://")):
                        return v

    # Fallback: scan lines from bottom up for a URL.
    for line in reversed(s.splitlines()):
        line = line.strip()
        if line.startswith(("http://", "https://")):
            return line

    # Last resort: return last non-empty line.
    return s.splitlines()[-1].strip()


@dataclass(frozen=True)
class CommandUploaderConfig:
    command_template: str
    timeout_s: int = 120


class CommandUploader:
    def __init__(self, cfg: CommandUploaderConfig):
        if not cfg.command_template.strip():
            raise ImageUploadError(
                'image_upload.mode="command" requires image_upload.command to be set (e.g. `picgo upload "{file}"`).'
            )
        self.cfg = cfg

    def upload(self, file_path: Path) -> str:
        cmd_str = self.cfg.command_template.replace("{file}", str(file_path))
        args = shlex.split(cmd_str)
        try:
            p = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.cfg.timeout_s,
            )
        except FileNotFoundError as e:
            raise ImageUploadError(f"Uploader command not found: {args[0]}") from e
        except subprocess.TimeoutExpired as e:
            raise ImageUploadError(f"Uploader timed out after {self.cfg.timeout_s}s") from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            msg = f"Uploader failed with exit code {e.returncode}"
            if stderr:
                msg = f"{msg}: {stderr}"
            raise ImageUploadError(msg) from e

        return _extract_url_from_stdout(p.stdout)


@dataclass(frozen=True)
class PicGoServerUploaderConfig:
    url: str
    secret: str = ""
    timeout_s: int = 120


class PicGoServerUploader:
    def __init__(self, cfg: PicGoServerUploaderConfig):
        if not cfg.url.strip():
            raise ImageUploadError('image_upload.mode="picgo_server" requires image_upload.picgo_server.url')
        self.cfg = cfg

    def upload(self, file_path: Path) -> str:
        # PicGo server commonly supports:
        # - JSON: {"list": ["/abs/path/to/file.png"]} (default)
        # - multipart/form-data (newer versions): key "files" (plural)
        headers = {}
        if self.cfg.secret.strip():
            headers["X-PicGo-Secret"] = self.cfg.secret.strip()

        # 1) Try JSON upload (most common / required by older servers).
        try:
            r = requests.post(
                self.cfg.url,
                json={"list": [str(file_path)]},
                headers=headers,
                timeout=self.cfg.timeout_s,
            )
        except requests.RequestException as e:
            raise ImageUploadError(f"PicGo server request failed: {e}") from e

        # If JSON upload fails, try multipart as a fallback.
        if r.status_code >= 400:
            raise ImageUploadError(f"PicGo server returned HTTP {r.status_code}: {r.text}")

        payload = None
        try:
            payload = r.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict) and payload.get("success") is False:
            msg = payload.get("message") or payload.get("msg") or r.text
            # Some servers specifically complain about JSON; try multipart with key "files".
            if isinstance(msg, str) and "Not sending data in JSON format" in msg:
                with open(file_path, "rb") as f:
                    files = [("files", (file_path.name, f))]
                    try:
                        r2 = requests.post(
                            self.cfg.url, files=files, headers=headers, timeout=self.cfg.timeout_s
                        )
                    except requests.RequestException as e:
                        raise ImageUploadError(f"PicGo server request failed: {e}") from e

                if r2.status_code >= 400:
                    raise ImageUploadError(f"PicGo server returned HTTP {r2.status_code}: {r2.text}")

                try:
                    payload2 = r2.json()
                except ValueError:
                    payload2 = None
                if isinstance(payload2, dict) and payload2.get("success") is False:
                    msg2 = payload2.get("message") or payload2.get("msg") or r2.text
                    raise ImageUploadError(f"PicGo server upload failed: {msg2}")
                return _extract_url_from_stdout(json.dumps(payload2) if payload2 is not None else r2.text)

            raise ImageUploadError(f"PicGo server upload failed: {msg}")

        return _extract_url_from_stdout(json.dumps(payload) if payload is not None else r.text)


def iter_markdown_files(output_dir: Path) -> Iterator[Path]:
    yield from output_dir.glob("**/*.md")


def _parse_md_link_target(inner: str) -> Tuple[str, str]:
    """Return (target, rest) where rest includes any title part."""
    s = inner.strip()
    if s.startswith("<") and s.endswith(">"):
        target = s[1:-1].strip()
        return target, ""  # uncommon to have titles inside <...>

    # Split off optional title: path "title" / path 'title' / path (title)
    # We keep it simple: first whitespace splits.
    parts = s.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " " + parts[1]


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_HTML_IMG_RE = re.compile(r"""<img\s+[^>]*src=(["'])(.*?)\1""", re.IGNORECASE)


def _iter_local_image_paths_from_md_text(md_text: str, output_dir: Path) -> Iterator[Path]:
    output_dir = output_dir.resolve()

    for m in _MD_IMAGE_RE.finditer(md_text):
        inner = m.group(1)
        target, _rest = _parse_md_link_target(inner)
        if not target or target.startswith(("http://", "https://", "data:")):
            continue
        local = (output_dir / target).resolve()
        try:
            local.relative_to(output_dir)
        except ValueError:
            continue
        if local.exists() and local.is_file() and _looks_like_image(local):
            yield local

    for m in _HTML_IMG_RE.finditer(md_text):
        target = (m.group(2) or "").strip()
        if not target or target.startswith(("http://", "https://", "data:")):
            continue
        local = (output_dir / target).resolve()
        try:
            local.relative_to(output_dir)
        except ValueError:
            continue
        if local.exists() and local.is_file() and _looks_like_image(local):
            yield local


def collect_local_images_from_markdown(output_dir: Path) -> List[Path]:
    """Collect local image files referenced by Markdown files under output_dir (deduped, sorted)."""
    output_dir = output_dir.resolve()
    seen: Set[Path] = set()

    for md_path in iter_markdown_files(output_dir):
        text = md_path.read_text(encoding="utf-8")
        for p in _iter_local_image_paths_from_md_text(text, output_dir):
            seen.add(p)

    return sorted(seen)


def rewrite_markdown_image_links(
    md_text: str,
    output_dir: Path,
    resolve_to_url,
) -> str:
    """Rewrite local image links in Markdown to URLs via resolve_to_url(local_path)->url."""

    def md_repl(m: re.Match) -> str:
        inner = m.group(1)
        target, rest = _parse_md_link_target(inner)
        if target.startswith(("http://", "https://", "data:")):
            return m.group(0)

        # Resolve relative paths against output_dir
        local = (output_dir / target).resolve()
        try:
            local.relative_to(output_dir.resolve())
        except ValueError:
            return m.group(0)

        if not local.exists() or not local.is_file() or not _looks_like_image(local):
            return m.group(0)

        url = resolve_to_url(local)
        return m.group(0).replace(inner, f"{url}{rest}")

    def html_repl(m: re.Match) -> str:
        quote = m.group(1)
        target = m.group(2).strip()
        if target.startswith(("http://", "https://", "data:")):
            return m.group(0)

        local = (output_dir / target).resolve()
        try:
            local.relative_to(output_dir.resolve())
        except ValueError:
            return m.group(0)

        if not local.exists() or not local.is_file() or not _looks_like_image(local):
            return m.group(0)

        url = resolve_to_url(local)
        return m.group(0).replace(f"src={quote}{target}{quote}", f"src={quote}{url}{quote}")

    md_text = _MD_IMAGE_RE.sub(md_repl, md_text)
    md_text = _HTML_IMG_RE.sub(html_repl, md_text)
    return md_text


def upload_images_and_rewrite_markdown(
    output_dir: Path,
    mode: str,
    command: str = "",
    picgo_server_url: str = "",
    picgo_server_secret: str = "",
) -> Dict[Path, str]:
    """Upload images referenced by markdown files under output_dir and rewrite links in-place.

    Returns:
        Mapping of local image path -> uploaded URL for images that were uploaded.
    """
    output_dir = output_dir.resolve()
    uploaded: Dict[Path, str] = {}

    if mode == "command":
        uploader = CommandUploader(CommandUploaderConfig(command_template=command))
    elif mode == "picgo_server":
        uploader = PicGoServerUploader(
            PicGoServerUploaderConfig(url=picgo_server_url, secret=picgo_server_secret)
        )
    else:
        raise ImageUploadError(f"Unknown image_upload.mode: {mode!r}")

    def resolve_to_url(local_path: Path) -> str:
        if local_path in uploaded:
            return uploaded[local_path]
        url = uploader.upload(local_path)
        uploaded[local_path] = url
        return url

    for md_path in iter_markdown_files(output_dir):
        original = md_path.read_text(encoding="utf-8")
        rewritten = rewrite_markdown_image_links(original, output_dir, resolve_to_url)
        if rewritten != original:
            md_path.write_text(rewritten, encoding="utf-8")

    return uploaded
