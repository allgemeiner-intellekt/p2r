# 05 - Image Upload Integration + Failure Fallback

## Goal

Integrate existing image upload + rewrite feature with the new export flow, and add a robust fallback:

- If upload is enabled and succeeds:
  - rewrite md links to remote URLs
  - then it becomes safe to discard `images/` by default
- If upload or rewrite fails:
  - do not try to “minimal export”
  - instead move the entire workdir to a configured failure directory
  - clearly warn the user and point them to the folder

## Depends On

- Step 03 (workdir exists and is separate from export)
- Step 04 (keep_images logic; upload success may affect images_dir safety)
- Existing `src/p2r/image_upload.py`

## Touchpoints

- `src/p2r/cli.py`
- `src/p2r/image_upload.py` (likely no changes, but may need a small adapter)
- `src/p2r/config.py` (reads `output.failure_dir`)

## Implementation Steps

1. Compute “upload_images enabled”:
   - effective value is:
     - CLI `--upload-images/--no-upload-images` if provided
     - else profile `upload_images` if not null
     - else global `image_upload.enabled`
2. If enabled:
   - run existing upload+rewrite on **workdir** (not export dir)
   - if it raises `ImageUploadError`:
     - trigger fallback (below)
3. Fallback behavior:
   - determine `failure_root = cfg.output.failure_dir or "./p2r_failed"`
   - move workdir => `<failure_root>/<pdf_stem>_vN/`
   - print a yellow warning:
     - upload failed
     - minimal export skipped
     - full output preserved at path
   - exit code `0` (conversion result is still usable)
4. On success:
   - proceed to export rules (steps 03/04)
   - default keep_images=false is now safe because md should contain URLs

## Acceptance Criteria

- When upload fails, user never loses files; they get a folder with everything.
- When upload succeeds, md links are rewritten and minimal export contains no local images by default.

## Tests

- Monkeypatch uploader to throw => fallback path created and contains expected files.
- Monkeypatch uploader to succeed => rewritten md exported correctly.

