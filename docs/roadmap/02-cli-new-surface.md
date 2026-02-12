# 02 - CLI New Surface (`p2r PDF_FILE`, `--profile`, new options)

## Goal

Expose the new user-facing CLI without breaking existing users:

- `p2r [OPTIONS] PDF_FILE` performs convert+export
- `--profile/-p NAME` selects a profile (default: `default_profile`)
- New options override profile settings:
  - `--md-dir`, `--html-dir`
  - `--keep-images/--no-keep-images`, `--images-dir`
  - `--keep-raw/--no-keep-raw`, `--raw-dir`
  - `-o/--output` becomes “final export dir override”
  - keep existing: `--model`, `--html/--no-html`, `--upload-images/--no-upload-images`
- Add `p2r config` command (actual implementation in step 06, but command plumbing can land here)

## Depends On

- `docs/roadmap/01-config-v2-profiles.md` (need `default_profile` and profile selection)

## Touchpoints

- `src/p2r/cli.py`
- `src/p2r/config.py` (read config)

## Implementation Steps

1. Re-shape click entrypoint:
   - Keep `@click.group()` for subcommands.
   - Add a **default command** behavior so `p2r file.pdf` works:
     - Option A (recommended): add a group `invoke_without_command=True` and accept `pdf_file` as argument on the group.
     - Option B: keep group but add a `convert` command and also register a top-level command named `p2r` via `main` with default command dispatch.
   - Pick one and make help output clear.
2. Introduce `--profile/-p` on the top-level convert path.
3. Add override options:
   - Make them all optional; only provided options override merged settings.
4. Deprecation strategy for old commands:
   - Keep existing `convert/show-config/config-token/upload-images` but set `hidden=True` and print deprecation note.
   - Or, if you want a clean break, keep them visible for now; but roadmap assumes hidden to simplify UX.
5. Parsing and merge:
   - Load config.
   - Resolve profile by `--profile` or config `default_profile`.
   - Build an “effective settings” object (from step 01 helper).

## Reserved Names (for profile naming)

Even though we are not using `--NAME` profiles anymore, we still want to reserve names to avoid confusion in docs:

- `config`, `convert`, `show-config`, `config-token`, `upload-images`

## Acceptance Criteria

- `p2r test-paper.pdf` runs without specifying a subcommand.
- `p2r -p default test-paper.pdf` works.
- `p2r config` subcommand exists (implementation in step 06).

## Tests To Add (Now)

- CLI smoke test: invokes `p2r file.pdf` and verifies it calls MinerU client once (monkeypatch).
- CLI merge test: `--profile` selection and per-option override precedence.

