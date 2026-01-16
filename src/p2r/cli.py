"""Command-line interface for p2r."""

import sys
import tempfile
from pathlib import Path
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from . import __version__
from .mineru import MinerUClient, MinerUError
from .config import get_config_path, get_api_token, update_token


console = Console()


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
def convert(pdf_file: Path, output: Path, model: str, html: bool):
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
    from .config import load_config

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
    else:
        console.print("[yellow]⚠[/yellow] Configuration file does not exist")
        console.print("It will be created automatically on first use.")


if __name__ == "__main__":
    main()
