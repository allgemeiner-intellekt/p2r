# 01 - Config v2 (Profiles + Migration)

## Goal

Introduce a v2 JSON config that supports:

- `profiles` (multiple named profiles)
- `default_profile`
- profile-scoped export behavior (md/html dirs, keep_images/raw, optional dirs)
- `ui.editor` (for `p2r config`)
- `output.failure_dir` (for image upload failure fallback)

Must remain backward compatible with existing `~/.p2r_config.json`.

## Depends On

- Nothing. This is the foundation.

## Touchpoints

- `src/p2r/config.py`
- (optional) add a small helper module: `src/p2r/profile.py` (recommended if config logic grows)

## Proposed Config Shape (v2)

Top-level:

- `version`: `2`
- `default_profile`: `"default"` (default)
- `profiles`: object with at least `default`
- `mineru`: keep existing
- `image_upload`: keep existing
- `ui.editor`: string (default `""`)
- `output.temp_dir`: keep existing
- `output.failure_dir`: string|null (default `null`)

Profile:

- `export.markdown_dir`: string (default `"."`)
- `export.html_dir`: string (default `"."`)
- `export.keep_images`: bool (default `false`)
- `export.images_dir`: string|null (default `null`)
- `export.keep_raw`: bool (default `false`)
- `export.raw_dir`: string|null (default `null`)
- `html`: bool (default `true`)
- `upload_images`: bool|null (default `null` meaning “inherit global image_upload.enabled”)

## Implementation Steps (Decision-Complete)

1. Update `get_default_config()` to emit v2 shape:
   - include `version/default_profile/profiles.default/ui/output.failure_dir`
2. Update `load_config()`:
   - after reading JSON/defaults, ensure `version` exists; if missing => treat as v1
   - migrate v1 => v2 in-memory:
     - set `version=2`
     - create `profiles.default` from defaults
     - set `default_profile="default"`
     - preserve existing known keys (`mineru`, `output.temp_dir`, `image_upload`) by merging into v2 result
   - best-effort writeback via `save_config()` (same behavior you already use elsewhere)
3. Add helpers (either in `config.py` or a new module) for later stages:
   - `get_profile(cfg: dict, name: str) -> dict` (validate existence, helpful error)
   - `get_effective_settings(cfg, profile_name, cli_overrides) -> dataclass/dict`
     - this should not do any IO; purely merges profile + cli + globals
4. Validation rules (fail fast with clear errors):
   - `default_profile` must exist in `profiles`
   - profile names must be non-empty and not collide with reserved CLI options (we will define the reserved list in step 02)
   - path-like fields can be relative; they will be resolved later (export step)

## Acceptance Criteria

- Running `load_config()` on an existing v1 config yields a v2 config dict with `profiles/default_profile`.
- A fresh install produces a v2 config file.
- Existing features (token, api_base_url, image_upload env overrides) still work.

## Tests To Add (Now)

- New tests in `tests/` that:
  - create a v1 JSON in a temp config path and verify `load_config()` migrates fields
  - verify `default_profile` existence validation

