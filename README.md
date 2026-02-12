# p2r

`p2r` is a small Python CLI that sends a PDF to the MinerU cloud API and downloads the extracted results (Markdown + JSON by default, with optional HTML).

## What you get

- `p2r convert ...` CLI with a Rich progress display
- Config stored at `~/.p2r_config.json` (permissions set to `0600`)
- Optional HTML output (enabled by default)
- Output folder cleanup: raw/debug artifacts get moved into `raw/`
- Optional image upload (PicGo) + automatic Markdown link rewriting (with progress)

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

## Configure MinerU

Two supported ways:

1) Save token to the config file:

```bash
p2r config-token YOUR_TOKEN
```

2) Use an environment variable (takes precedence over the config file):

```bash
export P2R_MINERU_TOKEN=YOUR_TOKEN
```

Optional: override the API base URL (useful for debugging/self-hosting):

```bash
export P2R_MINERU_API_BASE_URL=https://mineru.net/api/v4
```

To inspect what `p2r` sees:

```bash
p2r show-config
```

Config file location:

- Default: `~/.p2r_config.json`
- Override (useful for CI/sandbox environments): set `P2R_CONFIG_PATH=/path/to/config.json`

## Optional: Upload images (PicGo / image bed) and rewrite Markdown links

If you want `p2r` to automatically upload extracted images (e.g. `images/*.png`) to an image bed and rewrite
Markdown image links to remote URLs, enable `image_upload` in the config file (`~/.p2r_config.json` by default).

Two modes are supported:

1) `command` (recommended): run a local command per image and read the URL from stdout.

Example using PicGo CLI (ensure `picgo` is available in `PATH`):

```json
{
  "image_upload": {
    "enabled": true,
    "mode": "command",
    "command": "picgo upload \"{file}\""
  }
}
```

2) `picgo_server`: upload to a local HTTP endpoint (commonly provided by PicGo server plugins).

```json
{
  "image_upload": {
    "enabled": true,
    "mode": "picgo_server",
    "picgo_server": { "url": "http://127.0.0.1:36677/upload", "secret": "" }
  }
}
```

Notes for PicGo App Server:

- `p2r` will first try a JSON request that points PicGo to a local file path (common behavior):
  - `POST /upload` with JSON body like `{"list":["/absolute/path/to/image.png"]}`
  - This means PicGo must be running on the same machine and able to read the file path.
- If your PicGo Server has a secret enabled, set it as `picgo_server.secret` (sent as `X-PicGo-Secret`).

You can also override via env vars:

- `P2R_IMAGE_UPLOAD_ENABLED=1`
- `P2R_IMAGE_UPLOAD_MODE=command|picgo_server`
- `P2R_IMAGE_UPLOAD_COMMAND=...`
- `P2R_PICGO_SERVER_URL=http://127.0.0.1:36677/upload`
- `P2R_PICGO_SERVER_SECRET=...`

What gets uploaded / rewritten:

- Only local images that are referenced by Markdown files under the output directory are uploaded (deduped by path).
- Links are rewritten for both Markdown image syntax `![](images/x.png)` and HTML `<img src="images/x.png">` inside `.md`.
- When enabled, `p2r` shows a two-stage progress UI:
  - Uploading images (N/N)
  - Rewriting markdown files (M/M)

## Usage

Convert a PDF (default output directory is a temporary folder):

```bash
p2r convert paper.pdf
```

Notes:

- PDFs over 200MB are rejected before upload.

Write into a specific directory:

```bash
p2r convert paper.pdf -o ./out
```

Model selection (`vlm` is the CLI default in this repo):

```bash
p2r convert paper.pdf --model vlm
p2r convert paper.pdf --model pipeline
```

HTML output (enabled by default):

```bash
p2r convert paper.pdf --no-html
```

Image upload can be toggled per run:

```bash
p2r convert paper.pdf -o ./out --upload-images
p2r convert paper.pdf -o ./out --no-upload-images
```

If you already have an output folder and only want to upload + rewrite:

```bash
p2r upload-images ./out
```

## Troubleshooting

Config changes not taking effect:

- Check the config path and key settings:
  - `p2r show-config`
- Validate your JSON config file:
  - `python3 -m json.tool ~/.p2r_config.json > /tmp/p2r_config.validated.json`

PicGo Server upload fails:

- Verify `image_upload.picgo_server.url` and (if enabled) `image_upload.picgo_server.secret`.
- If PicGo returns `success=false`, `p2r` will fail fast and stop (to avoid rewriting Markdown with bad links).

## Output layout

MinerU returns a ZIP that `p2r` extracts into your output directory. Typical contents:

- `full.md` (primary Markdown)
- `images/` (assets)
- `raw/` (moved here if present: `layout.json`, `*_content_list.json`, `*_model.json`, `*_origin.pdf`)

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
pytest
```

## License

MIT (see `LICENSE`).
