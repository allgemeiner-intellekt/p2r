# 04 - Keep Images/Raw + Bundling Rules

## Goal

Support “keep_images / keep_raw” while preventing broken relative references:

- Default: do not keep `images/` and `raw/`.
- When keeping assets, export to a bundle dir `<export_root>/<pdf_stem>/` to maintain relative links.
- Only allow `images_dir/raw_dir` to differ from bundle dir when it is safe (e.g. images already rewritten to URLs).

## Depends On

- Step 03 (export routing; we need a concrete export mechanism to extend)

## Touchpoints

- `src/p2r/cli.py`
- `src/p2r/export.py` (if created)

## Implementation Steps

1. Extend effective settings:
   - resolve booleans `keep_images/keep_raw`
2. Implement bundling:
   - If either keep flag is true:
     - compute `bundle_dir = <export_root>/<pdf_stem>_vN/`
     - export md/html into `bundle_dir` (still naming `<pdf_stem>.md/.html` when single)
     - copy/move `workdir/images` => `bundle_dir/images` if keep_images
     - copy/move `workdir/raw` => `bundle_dir/raw` if keep_raw
3. Safety rule for `images_dir`:
   - If `images_dir` is set and differs from bundle_dir:
     - allow only when upload_images is enabled and succeeded (images no longer needed locally)
     - otherwise warn and ignore images_dir (keep in bundle_dir/images)
4. Similar safety for `raw_dir` (raw usually not referenced; can be freely separated):
   - raw can be exported separately without breaking md/html, so allow `raw_dir` always.

## Acceptance Criteria

- `--keep-images` produces `<dest>/<stem>/...` with `images/` present.
- Without keep flags, no `images/` nor `raw/` is copied to final export targets.

## Tests

- keep_images => bundle dir created, images copied
- keep_raw => raw copied to configured raw_dir (and/or bundle dir depending on settings)
- images_dir ignored with warning when upload_images is disabled

