# 06 - `p2r config` (Edit Config)

## Goal

Provide a single, ergonomic config editing entrypoint:

- `p2r config` opens the JSON config file in the configured editor
- editor can be configured in config; otherwise uses `$VISUAL/$EDITOR`, then falls back

## Depends On

- Step 01 (config v2 adds `ui.editor`)
- Step 02 (CLI command exists)

## Touchpoints

- `src/p2r/cli.py`
- `src/p2r/config.py`

## Implementation Steps

1. Ensure config file exists:
   - call `load_config()` (it already creates defaults best-effort)
   - if file still does not exist (e.g. permission issues), print the path and error out
2. Select editor:
   - `cfg.ui.editor` if set and non-empty
   - else `$VISUAL`, then `$EDITOR`
   - else fallback:
     - unix/mac: `vim`
     - windows: `notepad`
3. Launch editor:
   - split editor command by shell-like rules (use `shlex.split`)
   - append config path as last arg
   - run via `subprocess.run(..., check=False)` without capturing output so it attaches to tty

## Acceptance Criteria

- `p2r config` opens the config in editor and returns the editor's exit code (or 0).

## Tests (Optional)

This is hard to test portably; focus on unit-testing “editor selection” function if you factor it out.

