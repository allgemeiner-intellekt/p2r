# p2r

`p2r` is a Python CLI that sends a PDF to the MinerU cloud API, downloads the extracted results, and exports Markdown/HTML into predictable locations for reading and further processing.

## What you get

- One-shot convert: `p2r paper.pdf` (Rich progress)
- Profile-based config (`profiles` + `default_profile`) in `~/.p2r_config.json` (permissions `0600`)
- Export routing:
  - Default: only export `paper.md` / `paper.html` (no images/raw clutter)
  - Optional: `--keep-images` / `--keep-raw` to keep assets
- Optional image upload (PicGo) + Markdown link rewriting
- Safe fallback: if image upload/rewrite fails, the full MinerU output is preserved under `./p2r_failed/` (or `output.failure_dir`)

## Requirements

- Python `>= 3.8` (use `python3`)
- A MinerU API token
- Internet access

## Install

### User install (recommended)

With `pipx` from a local checkout:

```bash
pipx install .
```

### Development install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

Tip: `./activate.sh` will activate `venv` and print common commands.

## Quick start

1) Initialize config (guided):

```bash
p2r init
```

During `init`, `p2r` will ask for your MinerU token and then ask whether you want to create a new profile now.
If you answer "no", `init` will save the default config (default profile: `default`) and exit.
You can always create additional profiles later with `p2r profile`.

2) Convert:

```bash
p2r paper.pdf
```

## Usage

Convert a PDF (exports into the profile-configured directories; extraction uses a temporary workdir that gets cleaned up):

```bash
p2r paper.pdf
```

Use a specific profile:

```bash
p2r -p reading paper.pdf
```

Override export locations for one run:

```bash
p2r paper.pdf --md-dir ./md --html-dir ./html
```

Export both Markdown and HTML under one root (unless `--md-dir/--html-dir` are provided):

```bash
p2r paper.pdf -o ./out
```

Model selection:

```bash
p2r paper.pdf --model vlm
p2r paper.pdf --model pipeline
```

HTML output (default comes from profile; typically enabled):

```bash
p2r paper.pdf --no-html
```

Keep assets (default profile does not keep `images/` or `raw/`):

```bash
p2r paper.pdf --keep-images
p2r paper.pdf --keep-raw
```

Image upload can be toggled per run:

```bash
p2r paper.pdf --upload-images
p2r paper.pdf --no-upload-images
```

Notes:

- PDFs over 200MB are rejected before upload.

## Config

Edit config:

```bash
p2r config
```

Notes:

- `p2r init` can optionally create a new profile and set it as `default_profile`.
- If you skip profile creation during `init`, the default profile remains `default` (export dirs are `.` / `.` until you change them).
- `p2r profile` creates a new profile later (without re-running token onboarding). By default it will prompt whether to set it as `default_profile` (default answer: "no").

Create a new profile (guided):

```bash
p2r profile
```

Create a new profile non-interactively:

```bash
p2r profile --name reading --md-dir ./md --html-dir ./html --set-default
```

Force "do not change default profile" (non-interactive):

```bash
p2r profile --name reading --md-dir ./md --html-dir ./html --no-set-default
```

Config file location:

- Default: `~/.p2r_config.json`
- Override (useful for CI/sandbox): `P2R_CONFIG_PATH=/path/to/config.json`

Config shape (v2, simplified example):

```json
{
  "version": 2,
  "default_profile": "reading",
  "profiles": {
    "reading": {
      "export": {
        "markdown_dir": "./md",
        "html_dir": "./html",
        "keep_images": false,
        "images_dir": null,
        "keep_raw": false,
        "raw_dir": null
      },
      "html": true,
      "upload_images": null
    }
  },
  "mineru": {
    "api_token": "YOUR_TOKEN",
    "api_base_url": "https://mineru.net/api/v4",
    "poll_interval": 3,
    "max_poll_time": 600
  },
  "output": {
    "temp_dir": "/tmp/p2r",
    "failure_dir": null
  },
  "ui": { "editor": "" },
  "image_upload": {
    "enabled": false,
    "mode": "picgo_server",
    "command": "",
    "picgo_server": { "url": "http://127.0.0.1:36677/upload", "secret": "" }
  }
}
```

Advanced env overrides:

- `P2R_MINERU_TOKEN` (takes precedence over config)
- `P2R_MINERU_API_BASE_URL`
- `P2R_IMAGE_UPLOAD_ENABLED=1`
- `P2R_IMAGE_UPLOAD_MODE=command|picgo_server`
- `P2R_IMAGE_UPLOAD_COMMAND=...`
- `P2R_PICGO_SERVER_URL=http://127.0.0.1:36677/upload`
- `P2R_PICGO_SERVER_SECRET=...`

## Optional: Upload images (PicGo) and rewrite Markdown links

Enable `image_upload` in config.

Two modes are supported:

1) `picgo_server` (default): upload to a local HTTP endpoint (commonly provided by PicGo server plugins).

2) `command`: run a local command per image and read the URL from stdout.

Notes for PicGo server:

- `p2r` sends `POST /upload` with JSON like `{"list":["/absolute/path/to/image.png"]}`.
- PicGo must be running on the same machine and able to read that file path.
- If upload/rewrite fails, `p2r` falls back to saving the full MinerU output under `./p2r_failed/` (or `output.failure_dir`).

## Output layout

MinerU returns a ZIP that `p2r` extracts into a temporary work directory. Typical workdir contents:

- `full.md`
- `images/`
- `raw/` (moved here if present: `layout.json`, `*_content_list.json`, `*_model.json`, `*_origin.pdf`)

Final exported output (default behavior, no assets):

- `./paper.md`
- `./paper.html` (if enabled and produced)

If you use `--keep-images/--keep-raw`, exports are bundled under `./paper/` (to preserve relative links).

## Repo layout

```
.
├── src/p2r/        # package code
├── tests/          # pytest tests
├── pyproject.toml  # packaging / deps / console script
└── test-paper.pdf  # sample PDF used for local testing
```

## Tests

```bash
./venv/bin/python -m pytest
```

## License

MIT (see `LICENSE`).
