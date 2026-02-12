# 07 - Tests + README Updates

## Goal

After core behavior is in place, make it stable:

- update and expand pytest coverage for new CLI/export/profile behavior
- update `README.md` to match the new UX and config schema

## Depends On

- Steps 01-06 implemented (or at least the parts you document)

## Touchpoints

- `tests/` (new tests and adjustments)
- `README.md`

## Test Plan (Must-Have)

1. Config migration:
   - v1 => v2 adds `profiles` and `default_profile`
2. CLI:
   - `p2r file.pdf` works (no subcommand)
   - `--profile` selection
   - option override precedence (CLI > profile > global/default)
3. Export:
   - single md/html => `<stem>.md/.html`
   - multiple md/html => `<stem>/...` structure
   - `--output` overrides final export dir
4. Keep assets:
   - keep_images => bundle dir contains images
   - keep_raw => raw exported as configured
5. Upload fallback:
   - upload fails => full workdir moved to failure_dir, minimal export skipped

## README Update Checklist

- Replace `p2r convert paper.pdf` examples with `p2r paper.pdf`
- Add profile examples:
  - config snippet with `profiles` and `default_profile`
  - example `p2r --profile reading paper.pdf`
- Document export routing:
  - md/html dirs + `--output` semantics
  - keep_images/raw behavior
- Document failure fallback directory and how to recover artifacts

