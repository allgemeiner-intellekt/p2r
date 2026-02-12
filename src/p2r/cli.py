"""Command-line interface for p2r."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from . import __version__
from .config import (
    ENV_TOKEN_KEY,
    get_api_token,
    get_config_path,
    get_default_profile_name,
    get_profile,
    get_default_config,
    get_default_profile,
    load_config,
    save_config,
    update_token,
)
from .export import (
    ExportError,
    export_single_file,
    export_tree,
    find_files_by_extension,
    unique_dir_path,
)
from .image_upload import (
    CommandUploader,
    CommandUploaderConfig,
    ImageUploadError,
    PicGoServerUploader,
    PicGoServerUploaderConfig,
    collect_local_images_from_markdown,
    iter_markdown_files,
    rewrite_markdown_image_links,
)
from .mineru import MinerUClient, MinerUError


console = Console()


def _upload_images_with_progress(
    *,
    output_dir: Path,
    mode: str,
    command: str,
    picgo_server_url: str,
    picgo_server_secret: str,
) -> int:
    output_dir = output_dir.resolve()
    md_files = list(iter_markdown_files(output_dir))
    images = collect_local_images_from_markdown(output_dir)

    if not md_files:
        console.print("[yellow]No Markdown files found; skipping image upload.[/yellow]")
        return 0
    if not images:
        console.print("[yellow]No local images referenced; skipping image upload.[/yellow]")
        return 0

    if mode == "command":
        uploader = CommandUploader(CommandUploaderConfig(command_template=command))
    elif mode == "picgo_server":
        uploader = PicGoServerUploader(
            PicGoServerUploaderConfig(url=picgo_server_url, secret=picgo_server_secret)
        )
    else:
        raise ImageUploadError(f"Unknown image_upload.mode: {mode!r}")

    uploaded: Dict[Path, str] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        upload_task = progress.add_task("Uploading images...", total=len(images))
        for i, img in enumerate(images, start=1):
            progress.update(
                upload_task,
                description=f"Uploading images ({i}/{len(images)}): {img.name}",
            )
            url = uploader.upload(img)
            uploaded[img] = url
            progress.advance(upload_task, 1)

    def resolve_to_url(local_path: Path) -> str:
        try:
            return uploaded[local_path]
        except KeyError as e:
            raise ImageUploadError(f"Missing uploaded URL for: {local_path}") from e

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        rewrite_task = progress.add_task("Rewriting markdown...", total=len(md_files))
        for i, md_path in enumerate(md_files, start=1):
            progress.update(
                rewrite_task,
                description=f"Rewriting markdown ({i}/{len(md_files)}): {md_path.name}",
            )
            original = md_path.read_text(encoding="utf-8")
            rewritten = rewrite_markdown_image_links(original, output_dir, resolve_to_url)
            if rewritten != original:
                md_path.write_text(rewritten, encoding="utf-8")
            progress.advance(rewrite_task, 1)

    return len(uploaded)


def _open_in_editor(editor_cmd: str, file_path: Path) -> int:
    args = shlex.split(editor_cmd.strip())
    if not args:
        raise RuntimeError("empty editor command")
    args.append(str(file_path))
    p = subprocess.run(args)
    return p.returncode


def _pick_editor(cfg: dict) -> str:
    ui = cfg.get("ui", {}) if isinstance(cfg, dict) else {}
    editor = (ui.get("editor") or "").strip()
    if editor:
        return editor

    env_editor = (os.getenv("VISUAL") or os.getenv("EDITOR") or "").strip()
    if env_editor:
        return env_editor

    if os.name == "nt":
        return "notepad"
    return "vim"


def _make_workdir(cfg: dict) -> Path:
    out_cfg = cfg.get("output", {}) if isinstance(cfg, dict) else {}
    parent = out_cfg.get("temp_dir")
    if isinstance(parent, str) and parent.strip():
        p = Path(parent).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="p2r_", dir=str(p)))
    return Path(tempfile.mkdtemp(prefix="p2r_"))


def _resolve_export_dirs(
    *,
    cfg: dict,
    profile_name: str,
    export_root: Optional[Path],
    md_dir: Optional[Path],
    html_dir: Optional[Path],
) -> tuple[Path, Path]:
    prof = get_profile(cfg, profile_name)
    export_cfg = prof.get("export", {}) if isinstance(prof, dict) else {}

    md_raw = export_cfg.get("markdown_dir", ".")
    html_raw = export_cfg.get("html_dir", ".")
    md_dest = Path(md_raw if isinstance(md_raw, str) and md_raw.strip() else ".").expanduser()
    html_dest = Path(html_raw if isinstance(html_raw, str) and html_raw.strip() else ".").expanduser()

    if export_root is not None:
        if md_dir is None:
            md_dest = export_root
        if html_dir is None:
            html_dest = export_root

    if md_dir is not None:
        md_dest = md_dir
    if html_dir is not None:
        html_dest = html_dir

    return md_dest, html_dest


def _resolve_html_enabled(*, cfg: dict, profile_name: str, html_flag: Optional[bool]) -> bool:
    if html_flag is not None:
        return html_flag
    prof = get_profile(cfg, profile_name)
    val = prof.get("html", True) if isinstance(prof, dict) else True
    return bool(val)


def _resolve_upload_images_enabled(
    *, cfg: dict, profile_name: str, upload_images_flag: Optional[bool]
) -> bool:
    img_cfg = cfg.get("image_upload", {}) if isinstance(cfg, dict) else {}
    enabled = bool(img_cfg.get("enabled", False))

    prof = get_profile(cfg, profile_name)
    if isinstance(prof, dict):
        prof_val = prof.get("upload_images")
        if prof_val is not None:
            enabled = bool(prof_val)

    if upload_images_flag is not None:
        enabled = bool(upload_images_flag)

    return enabled


def _resolve_keep_assets(
    *,
    cfg: dict,
    profile_name: str,
    keep_images_flag: Optional[bool],
    keep_raw_flag: Optional[bool],
    images_dir: Optional[Path],
    raw_dir: Optional[Path],
) -> tuple[bool, bool, Optional[Path], Optional[Path]]:
    prof = get_profile(cfg, profile_name)
    export_cfg = prof.get("export", {}) if isinstance(prof, dict) else {}

    keep_images = bool(export_cfg.get("keep_images", False))
    keep_raw = bool(export_cfg.get("keep_raw", False))

    if keep_images_flag is not None:
        keep_images = bool(keep_images_flag)
    if keep_raw_flag is not None:
        keep_raw = bool(keep_raw_flag)

    images_dir_eff = export_cfg.get("images_dir")
    raw_dir_eff = export_cfg.get("raw_dir")

    if images_dir is not None:
        images_dir_eff = images_dir
    elif isinstance(images_dir_eff, str) and images_dir_eff.strip():
        images_dir_eff = Path(images_dir_eff).expanduser()
    else:
        images_dir_eff = None

    if raw_dir is not None:
        raw_dir_eff = raw_dir
    elif isinstance(raw_dir_eff, str) and raw_dir_eff.strip():
        raw_dir_eff = Path(raw_dir_eff).expanduser()
    else:
        raw_dir_eff = None

    return keep_images, keep_raw, images_dir_eff, raw_dir_eff


def _copy_dir(src_dir: Path, dest_dir: Path) -> None:
    if not src_dir.exists() or not src_dir.is_dir():
        return
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_dir, dest_dir)


def _move_workdir_to_failure_dir(*, cfg: dict, workdir: Path, pdf_stem: str) -> Path:
    out_cfg = cfg.get("output", {}) if isinstance(cfg, dict) else {}
    failure_root = out_cfg.get("failure_dir")
    if isinstance(failure_root, str) and failure_root.strip():
        root = Path(failure_root).expanduser()
    else:
        root = Path.cwd() / "p2r_failed"

    root.mkdir(parents=True, exist_ok=True)
    dest = unique_dir_path(root / pdf_stem)
    shutil.move(str(workdir), str(dest))
    return dest


def _run_convert_and_export(
    *,
    pdf_file: Path,
    profile: Optional[str],
    export_root: Optional[Path],
    md_dir: Optional[Path],
    html_dir: Optional[Path],
    keep_images: Optional[bool],
    keep_raw: Optional[bool],
    images_dir: Optional[Path],
    raw_dir: Optional[Path],
    model: str,
    html_flag: Optional[bool],
    upload_images_flag: Optional[bool],
) -> None:
    cfg = load_config()

    profile_name = profile or get_default_profile_name(cfg)
    try:
        get_profile(cfg, profile_name)
    except Exception:
        console.print(f"[red]Error:[/red] Unknown profile: {profile_name!r}")
        console.print(f"Edit your config: {get_config_path()}")
        sys.exit(1)

    # Verify API token is configured
    try:
        get_api_token()
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"\nPlease configure your API token in {get_config_path()}")
        console.print(f"Or set the {ENV_TOKEN_KEY} environment variable.")
        sys.exit(1)

    md_dest, html_dest = _resolve_export_dirs(
        cfg=cfg,
        profile_name=profile_name,
        export_root=export_root,
        md_dir=md_dir,
        html_dir=html_dir,
    )

    html_enabled = _resolve_html_enabled(cfg=cfg, profile_name=profile_name, html_flag=html_flag)
    upload_images_enabled = _resolve_upload_images_enabled(
        cfg=cfg, profile_name=profile_name, upload_images_flag=upload_images_flag
    )
    keep_images_enabled, keep_raw_enabled, images_dir_eff, raw_dir_eff = _resolve_keep_assets(
        cfg=cfg,
        profile_name=profile_name,
        keep_images_flag=keep_images,
        keep_raw_flag=keep_raw,
        images_dir=images_dir,
        raw_dir=raw_dir,
    )

    client = MinerUClient()
    workdir = _make_workdir(cfg)

    console.print(f"\n[bold]Converting:[/bold] {pdf_file.name}")
    console.print(f"[bold]Profile:[/bold] {profile_name}")
    console.print(f"[bold]Model:[/bold] {model}")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Uploading file...", total=100)

            extra_formats = ["html"] if html_enabled else None
            for update in client.parse_pdf(
                pdf_file, workdir, model_version=model, extra_formats=extra_formats
            ):
                state = update.get("state")

                if state == "waiting-file":
                    progress.update(task, description="Waiting for file upload...", completed=20)
                elif state == "pending":
                    progress.update(task, description="Queued for processing...", completed=30)
                elif state == "running":
                    prog = update.get("progress", "")
                    progress.update(
                        task,
                        description=f"Parsing ({prog} pages)...",
                        completed=50,
                    )
                elif state == "converting":
                    progress.update(task, description="Converting to Markdown...", completed=80)
                elif state == "completed":
                    progress.update(task, description="Download complete!", completed=100)

    except MinerUError as e:
        console.print(f"\n[red]Error:[/red] {e}")
        shutil.rmtree(workdir, ignore_errors=True)
        sys.exit(1)

    upload_images_succeeded = False
    if upload_images_enabled:
        img_cfg = cfg.get("image_upload", {}) if isinstance(cfg, dict) else {}
        mode = img_cfg.get("mode", "command")
        cmd = img_cfg.get("command", "")
        picgo_url = img_cfg.get("picgo_server", {}).get("url", "")
        picgo_secret = img_cfg.get("picgo_server", {}).get("secret", "")

        console.print("\n[bold]Uploading images...[/bold]")
        try:
            uploaded_count = _upload_images_with_progress(
                output_dir=workdir,
                mode=mode,
                command=cmd,
                picgo_server_url=picgo_url,
                picgo_server_secret=picgo_secret,
            )
        except ImageUploadError as e:
            failure_out = _move_workdir_to_failure_dir(cfg=cfg, workdir=workdir, pdf_stem=pdf_file.stem)
            console.print(f"[yellow]Image upload/rewrite failed.[/yellow] {e}")
            console.print("[yellow]Falling back to full output mode (all files preserved).[/yellow]")
            console.print(f"[bold]Saved to:[/bold] {failure_out}")
            return
        console.print(f"[green]Uploaded[/green] {uploaded_count} images and rewrote Markdown links.")
        upload_images_succeeded = True

    # Export md/html to final destinations (default: current directory).
    pdf_stem = pdf_file.stem

    keep_any = keep_images_enabled or keep_raw_enabled
    bundle_dir: Optional[Path] = None
    if keep_any:
        bundle_base = export_root if export_root is not None else md_dest
        bundle_base = Path(bundle_base).expanduser()
        bundle_dir = unique_dir_path(bundle_base / pdf_stem)
        md_export_root = bundle_dir
        html_export_root = bundle_dir
    else:
        md_export_root = md_dest
        html_export_root = html_dest

    try:
        md_files = find_files_by_extension(workdir=workdir, ext="md")
        html_files = find_files_by_extension(workdir=workdir, ext="html") if html_enabled else []

        md_path: Optional[Path] = None
        md_multi_root: Optional[Path] = None
        if md_files:
            if len(md_files) == 1:
                md_path = export_single_file(src=md_files[0], dest_file=Path(md_export_root) / f"{pdf_stem}.md")
            else:
                if keep_any:
                    md_multi_root = export_tree(files=md_files, workdir=workdir, dest_root=Path(md_export_root))
                else:
                    md_multi_root = export_tree(
                        files=md_files,
                        workdir=workdir,
                        dest_root=unique_dir_path(Path(md_export_root) / pdf_stem),
                    )

        html_path: Optional[Path] = None
        html_multi_root: Optional[Path] = None
        if html_files:
            if len(html_files) == 1:
                html_path = export_single_file(
                    src=html_files[0], dest_file=Path(html_export_root) / f"{pdf_stem}.html"
                )
            else:
                if keep_any:
                    html_multi_root = export_tree(files=html_files, workdir=workdir, dest_root=Path(html_export_root))
                else:
                    html_multi_root = export_tree(
                        files=html_files,
                        workdir=workdir,
                        dest_root=unique_dir_path(Path(html_export_root) / pdf_stem),
                    )
    except ExportError as e:
        console.print(f"[red]Export error:[/red] {e}")
        shutil.rmtree(workdir, ignore_errors=True)
        sys.exit(1)

    # Copy assets if requested.
    if keep_any:
        assert bundle_dir is not None

        if keep_images_enabled:
            src_images = workdir / "images"
            if images_dir_eff is not None and images_dir_eff.resolve() != bundle_dir.resolve():
                if upload_images_succeeded:
                    doc_dir = unique_dir_path(Path(images_dir_eff) / pdf_stem)
                    _copy_dir(src_images, doc_dir / "images")
                else:
                    console.print(
                        "[yellow]images_dir is ignored because image upload is disabled; keeping images next to Markdown.[/yellow]"
                    )
                    _copy_dir(src_images, bundle_dir / "images")
            else:
                _copy_dir(src_images, bundle_dir / "images")

        if keep_raw_enabled:
            src_raw = workdir / "raw"
            if raw_dir_eff is not None:
                doc_dir = unique_dir_path(Path(raw_dir_eff) / pdf_stem)
                _copy_dir(src_raw, doc_dir / "raw")
            else:
                _copy_dir(src_raw, bundle_dir / "raw")

    console.print("\n[green]Success![/green] Exported files:")
    if md_path is not None:
        console.print(f"  - Markdown: {md_path}")
    if md_multi_root is not None and md_path is None:
        console.print(f"  - Markdown: {md_multi_root}")
    if html_path is not None:
        console.print(f"  - HTML: {html_path}")
    if html_multi_root is not None and html_path is None:
        console.print(f"  - HTML: {html_multi_root}")

    shutil.rmtree(workdir, ignore_errors=True)


@click.group()
@click.version_option(version=__version__)
def cli():
    """p2r - Convert a PDF to Markdown/HTML using MinerU."""
    pass


@cli.command()
@click.argument("pdf_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-p", "--profile", help="Profile name (default: from config)")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path, file_okay=False),
    help="Final export directory override",
)
@click.option(
    "--md-dir",
    type=click.Path(path_type=Path, file_okay=False),
    help="Markdown export directory (overrides profile; has priority over --output)",
)
@click.option(
    "--html-dir",
    type=click.Path(path_type=Path, file_okay=False),
    help="HTML export directory (overrides profile; has priority over --output)",
)
@click.option(
    "--model",
    type=click.Choice(["pipeline", "vlm"]),
    default="vlm",
    show_default=True,
    help="MinerU model version",
)
@click.option(
    "--html/--no-html",
    default=None,
    help="Request HTML output from MinerU (default: from profile)",
)
@click.option(
    "--upload-images/--no-upload-images",
    default=None,
    help="Upload extracted images and rewrite Markdown links (default: from profile/config)",
)
@click.option(
    "--keep-images/--no-keep-images",
    default=None,
    help="Keep extracted images in the final output (default: from profile)",
)
@click.option(
    "--images-dir",
    type=click.Path(path_type=Path, file_okay=False),
    help="Where to save images (default: from profile; may be ignored to preserve relative links)",
)
@click.option(
    "--keep-raw/--no-keep-raw",
    default=None,
    help="Keep raw/debug artifacts in the final output (default: from profile)",
)
@click.option(
    "--raw-dir",
    type=click.Path(path_type=Path, file_okay=False),
    help="Where to save raw/debug artifacts (default: from profile)",
)
def convert(
    pdf_file: Path,
    profile: Optional[str],
    output: Optional[Path],
    md_dir: Optional[Path],
    html_dir: Optional[Path],
    model: str,
    html: Optional[bool],
    upload_images: Optional[bool],
    keep_images: Optional[bool],
    images_dir: Optional[Path],
    keep_raw: Optional[bool],
    raw_dir: Optional[Path],
):
    """Convert a PDF file to Markdown/HTML.

    You can omit the `convert` subcommand:

        p2r paper.pdf

    is equivalent to:

        p2r convert paper.pdf
    """
    _run_convert_and_export(
        pdf_file=pdf_file,
        profile=profile,
        export_root=output,
        md_dir=md_dir,
        html_dir=html_dir,
        keep_images=keep_images,
        keep_raw=keep_raw,
        images_dir=images_dir,
        raw_dir=raw_dir,
        model=model,
        html_flag=html,
        upload_images_flag=upload_images,
    )


@cli.command("config")
def config_cmd():
    """Open the config file in your editor."""
    cfg = load_config()
    config_path = get_config_path()

    if not config_path.exists():
        console.print(f"[red]Error:[/red] Config file does not exist: {config_path}")
        sys.exit(1)

    editor = _pick_editor(cfg)
    try:
        rc = _open_in_editor(editor, config_path)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Editor not found: {editor!r}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to open editor: {e}")
        sys.exit(1)

    raise SystemExit(rc)


@cli.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing config if it exists")
@click.option("-y", "--yes", is_flag=True, help="Do not prompt for confirmation when using --force")
def init_cmd(force: bool, yes: bool):
    """Initialize (or reset) your p2r configuration with guided prompts.

    This is intended for onboarding. It only asks for:
    - MinerU API token
    - one additional profile (name + export dirs)
    """
    config_path = get_config_path()
    if config_path.exists() and not force:
        console.print(f"[red]Error:[/red] Config already exists: {config_path}")
        console.print("Run `p2r init --force` to overwrite it.")
        raise SystemExit(1)

    if config_path.exists() and force and not yes:
        if not click.confirm(f"Overwrite existing config at {config_path}?", default=False):
            console.print("Aborted.")
            return

    cfg = get_default_config()

    console.print("[bold]MinerU settings[/bold]")
    token = click.prompt("MinerU API token", default="", show_default=False)
    if token.strip():
        cfg.setdefault("mineru", {})["api_token"] = token.strip()

    console.print("\n[bold]Profile[/bold]")
    name = click.prompt("Profile name", default="reading").strip()
    while not name or name in cfg.get("profiles", {}):
        name = click.prompt("Profile name (must be unique)", default=f"{name or 'reading'}_v2").strip()

    p = get_default_profile()
    export_cfg = p.setdefault("export", {})
    export_cfg["markdown_dir"] = click.prompt("Markdown export directory", default="./md")
    export_cfg["html_dir"] = click.prompt("HTML export directory", default="./html")

    cfg.setdefault("profiles", {})[name] = p
    cfg["default_profile"] = name

    save_config(cfg)

    console.print(f"\n[green]Saved[/green] config to: {config_path}")
    console.print(f"[bold]Default profile:[/bold] {cfg.get('default_profile')}")
    if not cfg.get("mineru", {}).get("api_token"):
        console.print(f"[yellow]Note:[/yellow] API token is empty; set it in {config_path} or via {ENV_TOKEN_KEY}.")


@cli.command(hidden=True)
@click.argument("token")
def config_token(token: str):
    """(Deprecated) Set the MinerU API token."""
    try:
        update_token(token)
        console.print("[green]Token saved successfully![/green]")
        console.print(f"Configuration file: {get_config_path()}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command(hidden=True)
def show_config():
    """(Deprecated) Show configuration file location and current settings."""
    config_path = get_config_path()
    console.print(f"[bold]Configuration file:[/bold] {config_path}")

    if config_path.exists():
        console.print("[green]✓[/green] Configuration file exists")

        try:
            token = get_api_token()
            masked_token = token[:8] + "..." + token[-8:] if len(token) > 16 else "***"
            console.print(f"[bold]API Token:[/bold] {masked_token}")
        except ValueError:
            console.print("[yellow]⚠[/yellow] API token not configured")

        cfg = load_config()
        console.print("\n[bold]Settings:[/bold]")
        console.print(f"  API Base URL: {cfg.get('mineru', {}).get('api_base_url')}")
        console.print(f"  Poll Interval: {cfg.get('mineru', {}).get('poll_interval')}s")
        console.print(f"  Max Poll Time: {cfg.get('mineru', {}).get('max_poll_time')}s")
        console.print(f"  Temp Directory: {cfg.get('output', {}).get('temp_dir')}")
        console.print(f"  Default Profile: {cfg.get('default_profile')}")
        img_cfg = cfg.get("image_upload", {})
        console.print(f"  Image Upload Enabled: {img_cfg.get('enabled', False)}")
        console.print(f"  Image Upload Mode: {img_cfg.get('mode', 'command')}")
    else:
        console.print("[yellow]⚠[/yellow] Configuration file does not exist")
        console.print("It will be created automatically on first use.")


@cli.command("upload-images", hidden=True)
@click.argument("output_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def upload_images_cmd(output_dir: Path):
    """(Deprecated) Upload images under an existing output directory and rewrite Markdown links."""
    cfg = load_config()
    img_cfg = cfg.get("image_upload", {}) if isinstance(cfg, dict) else {}

    mode = img_cfg.get("mode", "command")
    cmd = img_cfg.get("command", "")
    picgo_url = img_cfg.get("picgo_server", {}).get("url", "")
    picgo_secret = img_cfg.get("picgo_server", {}).get("secret", "")

    console.print(f"[bold]Uploading images in:[/bold] {output_dir}")
    try:
        uploaded_count = _upload_images_with_progress(
            output_dir=output_dir,
            mode=mode,
            command=cmd,
            picgo_server_url=picgo_url,
            picgo_server_secret=picgo_secret,
        )
    except ImageUploadError as e:
        console.print(f"[red]Image upload error:[/red] {e}")
        sys.exit(1)

    console.print(f"[green]Uploaded[/green] {uploaded_count} images and rewrote Markdown links.")


def main() -> None:
    """Console entrypoint.

    Allows `p2r PDF_FILE` by rewriting argv to `p2r convert PDF_FILE`.
    """
    argv = sys.argv[1:]
    if not argv:
        cli.main(prog_name="p2r")
        return

    # Keep top-level help intact.
    if argv[0] in {"-h", "--help"}:
        cli.main(args=argv, prog_name="p2r")
        return

    # If user explicitly types a subcommand, do not rewrite.
    if argv[0] in {"convert", "config", "init", "config-token", "show-config", "upload-images"}:
        cli.main(args=argv, prog_name="p2r")
        return

    cli.main(args=["convert", *argv], prog_name="p2r")


if __name__ == "__main__":
    main()
