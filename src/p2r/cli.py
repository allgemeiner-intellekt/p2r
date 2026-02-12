"""Command-line interface for p2r."""

import sys
import tempfile
from pathlib import Path
from typing import Optional, Dict
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from . import __version__
from .mineru import MinerUClient, MinerUError
from .config import get_config_path, get_api_token, update_token
from .config import load_config
from .image_upload import (
    ImageUploadError,
    collect_local_images_from_markdown,
    iter_markdown_files,
    rewrite_markdown_image_links,
    CommandUploader,
    CommandUploaderConfig,
    PicGoServerUploader,
    PicGoServerUploaderConfig,
)


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


@click.group()
@click.version_option(version=__version__)
def main():
    """p2r - Convert PDF papers to Markdown using MinerU."""
    pass


@main.command()
@click.argument("pdf_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output directory (default: temporary directory)",
)
@click.option(
    "--model",
    type=click.Choice(["pipeline", "vlm"]),
    default="vlm",
    help="MinerU model version (default: vlm)",
)
@click.option(
    "--html/--no-html",
    default=True,
    show_default=True,
    help="Request HTML output from MinerU (default: enabled)",
)
@click.option(
    "--upload-images/--no-upload-images",
    default=None,
    help="Upload extracted images to an image bed and rewrite Markdown links with progress (default: from config)",
)
def convert(pdf_file: Path, output: Path, model: str, html: bool, upload_images: Optional[bool]):
    """Convert a PDF file to Markdown.

    Example:
        p2r convert paper.pdf
        p2r convert paper.pdf -o ./output
    """
    try:
        # Verify API token is configured
        try:
            get_api_token()
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            console.print(
                f"\nPlease configure your API token in {get_config_path()}"
            )
            console.print("Or set the P2R_MINERU_TOKEN environment variable.")
            sys.exit(1)

        # Initialize client
        client = MinerUClient()

        # Create output directory
        if output is None:
            output = Path(tempfile.mkdtemp(prefix="p2r_"))
            console.print(f"Using temporary output directory: {output}")
        else:
            output.mkdir(parents=True, exist_ok=True)

        console.print(f"\n[bold]Converting:[/bold] {pdf_file.name}")
        console.print(f"[bold]Model:[/bold] {model}")

        # Parse PDF with progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            # Create initial task
            task = progress.add_task("Uploading file...", total=100)

            try:
                extra_formats = ["html"] if html else None
                for update in client.parse_pdf(
                    pdf_file, output, model_version=model, extra_formats=extra_formats
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
                        output_dir = update.get("output_dir")

            except MinerUError as e:
                console.print(f"\n[red]Error:[/red] {e}")
                sys.exit(1)

        # Success message
        console.print(f"\n[green]Success![/green] Files saved to: {output}")

        cfg = load_config()
        img_cfg = cfg.get("image_upload", {}) if isinstance(cfg, dict) else {}
        enabled = img_cfg.get("enabled", False)
        if upload_images is not None:
            enabled = upload_images

        if enabled:
            mode = img_cfg.get("mode", "command")
            cmd = img_cfg.get("command", "")
            picgo_url = img_cfg.get("picgo_server", {}).get("url", "")
            picgo_secret = img_cfg.get("picgo_server", {}).get("secret", "")
            console.print("\n[bold]Uploading images...[/bold]")
            try:
                uploaded_count = _upload_images_with_progress(
                    output_dir=output,
                    mode=mode,
                    command=cmd,
                    picgo_server_url=picgo_url,
                    picgo_server_secret=picgo_secret,
                )
            except ImageUploadError as e:
                console.print(f"[red]Image upload error:[/red] {e}")
                sys.exit(1)
            console.print(f"[green]Uploaded[/green] {uploaded_count} images and rewrote Markdown links.")

        # List output files
        if output.exists():
            md_files = list(output.glob("**/*.md"))
            html_files = list(output.glob("**/*.html"))
            if md_files:
                console.print(f"\nMarkdown files:")
                for md_file in md_files:
                    rel_path = md_file.relative_to(output)
                    console.print(f"  - {rel_path}")
            if html_files:
                console.print(f"\nHTML files:")
                for html_file in html_files:
                    rel_path = html_file.relative_to(output)
                    console.print(f"  - {rel_path}")

    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("token")
def config_token(token: str):
    """Set the MinerU API token.

    Example:
        p2r config-token your-api-token-here
    """
    try:
        update_token(token)
        console.print(f"[green]Token saved successfully![/green]")
        console.print(f"Configuration file: {get_config_path()}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
def show_config():
    """Show configuration file location and current settings."""
    config_path = get_config_path()
    console.print(f"[bold]Configuration file:[/bold] {config_path}")

    if config_path.exists():
        console.print(f"[green]✓[/green] Configuration file exists")

        try:
            token = get_api_token()
            masked_token = token[:8] + "..." + token[-8:] if len(token) > 16 else "***"
            console.print(f"[bold]API Token:[/bold] {masked_token}")
        except ValueError:
            console.print("[yellow]⚠[/yellow] API token not configured")

        cfg = load_config()
        console.print(f"\n[bold]Settings:[/bold]")
        console.print(f"  API Base URL: {cfg.get('mineru', {}).get('api_base_url')}")
        console.print(f"  Poll Interval: {cfg.get('mineru', {}).get('poll_interval')}s")
        console.print(f"  Max Poll Time: {cfg.get('mineru', {}).get('max_poll_time')}s")
        console.print(f"  Temp Directory: {cfg.get('output', {}).get('temp_dir')}")
        img_cfg = cfg.get("image_upload", {})
        console.print(f"  Image Upload Enabled: {img_cfg.get('enabled', False)}")
        console.print(f"  Image Upload Mode: {img_cfg.get('mode', 'command')}")
    else:
        console.print("[yellow]⚠[/yellow] Configuration file does not exist")
        console.print("It will be created automatically on first use.")


@main.command("upload-images")
@click.argument("output_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def upload_images_cmd(output_dir: Path):
    """Upload images under an existing output directory and rewrite Markdown links with progress."""
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


if __name__ == "__main__":
    main()
