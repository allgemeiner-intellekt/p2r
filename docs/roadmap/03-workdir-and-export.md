# 03 - Workdir + Export Routing (Core UX)

## Goal

Decouple “MinerU extraction workdir” from “final export location”, enabling:

- Always extract into a temporary workdir
- Export md/html into configured locations
- Default export behavior: md/html placed in current directory unless overridden
- `--output DIR` overrides final export root (not the workdir)

## Depends On

- Step 01 (config schema, effective settings)
- Step 02 (CLI plumbing and option parsing)

## Touchpoints

- `src/p2r/cli.py`
- `src/p2r/mineru.py` (no API change expected; just how `output_dir` is used)
- (new recommended) `src/p2r/export.py` (pure file operations and rules)

## Implementation Steps

1. Introduce “workdir always temp”:
   - In CLI, replace current behavior where `-o/--output` is the extraction dir.
   - Instead:
     - `workdir = tempfile.mkdtemp(prefix="p2r_", dir=cfg.output.temp_dir if set)`
     - pass `workdir` to `client.parse_pdf(...)`
2. Decide export destinations:
   - `md_dest = settings.export.markdown_dir`
   - `html_dest = settings.export.html_dir`
   - If `--output` is provided, treat it as `export_root` override:
     - `md_dest = export_root` unless user explicitly also passed `--md-dir`
     - `html_dest = export_root` unless user explicitly also passed `--html-dir`
3. Implement “single vs multiple” export rule:
   - Find markdown files under workdir (`**/*.md`).
   - Find html files under workdir (`**/*.html`).
   - If exactly one file of that type:
     - export as `<dest>/<pdf_stem>.md` or `<dest>/<pdf_stem>.html`
   - If multiple:
     - export to `<dest>/<pdf_stem>/...` preserving relative structure to avoid collisions.
4. Overwrite handling:
   - If target exists, auto-suffix `_v2/_v3...` (file or directory).
5. Cleanup:
   - On success, remove workdir.
   - On controlled fallback (step 05), preserve/move workdir instead.

## Acceptance Criteria

- `p2r a.pdf` results in:
  - `./a.md` (and `./a.html` when enabled and present)
  - no leftover images/raw by default (handled later; but workdir should be gone)
- `p2r a.pdf -o out/` results in:
  - `out/a.md` and `out/a.html`
- If MinerU outputs multiple `.md`, we do not overwrite; we create `out/a/` and keep structure.

## Tests

- Export placement tests (single md/html).
- Multi-file export test triggers folder mode.
- `--output` precedence vs explicit `--md-dir/--html-dir`.

