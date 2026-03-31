# Plan: Make p2r Agent-Friendly

## Context

p2r converts PDFs to Markdown via the MinerU cloud API. It works well for humans but is hard for AI agents (Claude Code, Cursor, etc.) to use because:
- Rich progress bars emit ANSI escape codes that pollute tool output
- No structured way to get the final output file path without parsing a decorated success message
- Exit codes are always 1 regardless of error type

The goal: make p2r a first-class tool for agents while keeping the human experience unchanged.

## Changes (3 phases, in order)

### Phase 1: Move all Rich output to stderr
**Files:** `src/p2r/cli.py` (line 51)

Change `console = Console()` → `console = Console(stderr=True)`.

This is the single biggest agent-friendliness win with the smallest change:
- Human users see no difference (stderr displays in terminal just like stdout)
- Agents/pipes get clean stdout (empty in human mode, JSON in `--json` mode)
- Rich auto-detects stderr is a TTY and keeps colors

### Phase 2: Structured exit codes
**Files:** `src/p2r/cli.py`

Define constants at the top of the file:
```python
EXIT_OK = 0
EXIT_GENERAL = 1
EXIT_CONFIG = 2
EXIT_API = 3
EXIT_EXPORT = 4
```

Update call sites:
- Line 343 (unknown profile) → `sys.exit(EXIT_CONFIG)`
- Line 352 (missing token) → `sys.exit(EXIT_CONFIG)`
- Line 417 (MinerU error) → `sys.exit(EXIT_API)`
- Line 498 (export error) → `sys.exit(EXIT_EXPORT)`

### Phase 3: `--json` flag
**Files:** `src/p2r/cli.py`

Add `--json` / `--no-json` flag to the `convert` command (default: `False`).

When `--json` is set:
1. **Suppress Rich progress bars** — skip the `Progress()` context managers entirely for both PDF conversion (lines 383-412) and image upload (lines 124-139, 147-164). Just iterate the generators silently.
2. **Emit a single JSON object to stdout on completion:**
   ```json
   {
     "success": true,
     "markdown_path": "/absolute/path/paper.md",
     "html_path": "/absolute/path/paper.html"
   }
   ```
3. **On error, emit JSON to stdout before exiting:**
   ```json
   {
     "success": false,
     "error": "Extraction failed: timeout",
     "exit_code": 3
   }
   ```
4. **On image-upload fallback:**
   ```json
   {
     "success": true,
     "markdown_path": "/absolute/path/p2r_failed/paper/full.md",
     "warning": "Image upload failed; raw output preserved"
   }
   ```

Implementation details:
- Add `--json` flag to `convert` Click command definition
- Thread `json_mode: bool` parameter into `_run_convert_and_export()`
- Add helper: `_emit_json(data: dict) -> None` that does `print(json.dumps(data))` to stdout
- In `_run_convert_and_export()`:
  - Wrap progress bars in `if not json_mode:` guards
  - Replace the success output block (lines 526-534) with conditional: human print vs JSON emit
  - Replace each error exit with conditional: human print + exit vs JSON emit + exit
- In `_upload_images_with_progress()`: add `json_mode` parameter; skip `Progress()` when true

## Files to modify
- `src/p2r/cli.py` — all three phases

## Files that do NOT change
- `src/p2r/mineru.py`
- `src/p2r/export.py`
- `src/p2r/config.py`
- `src/p2r/image_upload.py`
- `pyproject.toml`

## Verification

1. **Human mode unchanged**: `p2r test-paper.pdf` shows same Rich progress bars and colored output
2. **JSON mode**: `p2r test-paper.pdf --json` prints one JSON line to stdout, progress/status to stderr
3. **Composable**: `p2r test-paper.pdf --json 2>/dev/null | jq -r .markdown_path` outputs just the path
4. **Exit codes**: verify specific codes for config/API/export errors
5. **Existing tests**: `pytest tests/` should pass (may need minor updates for stderr console change)
