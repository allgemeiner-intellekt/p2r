# Plan: Make p2r CLI Agent-Friendly

## Overview

Three improvements to make `p2r` usable by AI agents and scripts while preserving the current human-friendly Rich output as the default experience.

## Design Decisions

### Q1: `--json` flag vs `--quiet` vs both?
**Answer: `--json` only.** A `--quiet` flag that prints bare paths is tempting but under-specified (what if there are multiple outputs? what about errors?). JSON gives structured, extensible output that agents can trivially parse. Agents that want just the markdown path do `jq -r .markdown_path`. One flag is simpler to maintain.

### Q2: Auto-detect non-TTY?
**Answer: Yes, with override.** When stdout is not a TTY, automatically switch to JSON output. This means `p2r paper.pdf | jq .` just works. Add `--human` flag to force Rich output even in pipes (rare but useful for `less -R`). Add `--json` flag to force JSON even in a TTY (for testing/debugging). The detection logic: `--json` flag > `--human` flag > `sys.stdout.isatty()`.

### Q3: Page range — MinerU API support?
**Answer: Client-side PDF splitting.** The MinerU API payload (`files: [{name: ...}]`) has no page range parameter, and the progress response reports `extracted_pages/total_pages` which confirms server-side full extraction. We must split the PDF client-side before upload. Use `pypdf` (lightweight, pure-Python, well-maintained successor to PyPDF2) as an optional dependency.

### Q4: `--pages` flag format?
**Answer: `--pages 1-10` with support for comma-separated ranges.** Examples: `--pages 5`, `--pages 1-10`, `--pages 1-5,10-15`. This matches common conventions (e.g., `pdftk`, print dialogs). Pages are 1-indexed for human friendliness.

### Q5: Exit codes?
**Answer: Systematic exit codes.**
- 0: success
- 1: general/unknown error (current behavior, keep)
- 2: configuration error (missing token, bad profile)
- 3: API error (MinerU returned error, timeout)
- 4: export error (file write failures)

### Q6: JSON to stdout or stderr?
**Answer: JSON result to stdout, progress to stderr.** This follows Unix convention. In JSON mode, the Rich progress bars are suppressed entirely (they are meaningless to agents). Instead, progress updates go to stderr as simple single-line status messages (or are suppressed with `--quiet` if we add it later).

---

## Implementation Plan

### Phase 1: Output Mode Infrastructure (cli.py)

**Goal:** Add `--json` / `--human` flags and TTY auto-detection.

**File: `src/p2r/cli.py`**

1. Add a module-level helper to determine output mode:

```python
import json as _json

def _resolve_output_mode(json_flag: bool, human_flag: bool) -> str:
    """Return 'json' or 'human'."""
    if json_flag:
        return "json"
    if human_flag:
        return "human"
    return "human" if sys.stdout.isatty() else "json"
```

2. Create two Console instances — one for stderr (progress), one for stdout (results):

```python
# Replace the module-level `console = Console()` with a factory:
def _make_consoles(output_mode: str):
    if output_mode == "json":
        # Progress goes to stderr, no markup; result goes to stdout as plain text
        progress_console = Console(stderr=True, no_color=True, markup=False)
        result_console = None  # We'll print JSON directly to stdout
    else:
        progress_console = Console(stderr=True)
        result_console = Console()  # stdout with Rich markup
    return progress_console, result_console
```

3. Add `--json` and `--human` options to the `convert` command (lines 546-601):

```python
@click.option("--json", "json_flag", is_flag=True, default=False,
              help="Force JSON output (default when stdout is not a TTY)")
@click.option("--human", "human_flag", is_flag=True, default=False,
              help="Force human-readable Rich output even when piped")
```

4. Modify `_run_convert_and_export()` signature to accept `output_mode: str` parameter.

5. In JSON mode, replace Rich progress with stderr status lines:
   - Instead of `Progress(SpinnerColumn, ...)`, emit `{"state": "uploading", "progress": 20}` lines to stderr
   - Or simpler: just suppress progress entirely in JSON mode (agents don't need it)

6. At the end of `_run_convert_and_export()`, in JSON mode, print a JSON object to stdout:

```python
result = {
    "success": True,
    "markdown_path": str(md_path) if md_path else str(md_multi_root),
    "html_path": str(html_path) if html_path else str(html_multi_root) if html_enabled else None,
    "images_uploaded": upload_images_succeeded,
    "pdf_file": str(pdf_file),
}
print(_json.dumps(result))
```

7. For errors in JSON mode, print JSON error to stdout and exit with appropriate code:

```python
result = {"success": False, "error": str(e), "error_type": "api_error"}
print(_json.dumps(result))
sys.exit(3)
```

**Key change locations in cli.py:**
- Line 51: Replace `console = Console()` with lazy initialization
- Lines 320-536: `_run_convert_and_export()` — thread `output_mode` through, conditionally use Rich vs plain output
- Lines 382-412: Progress block — skip Rich Progress in JSON mode
- Lines 414-417: Error handling — JSON error output
- Lines 526-536: Success output — JSON result output
- Lines 546-639: `convert()` command — add flags, resolve mode, pass to `_run_convert_and_export`
- Lines 833-857: `main()` — pass through new flags

### Phase 2: Page Range Support

**Goal:** `--pages 1-10` flag that extracts a page subset before uploading to MinerU.

**File: `pyproject.toml`**

1. Add `pypdf` as an optional dependency:

```toml
[project.optional-dependencies]
pages = ["pypdf>=3.0.0"]
dev = [
    "pypdf>=3.0.0",
    "pytest>=7.0.0",
    ...
]

dependencies = [
    "requests>=2.28.0",
    "click>=8.0.0",
    "rich>=13.0.0",
    # pypdf is optional; only needed for --pages
]
```

**File: `src/p2r/pages.py` (new file)**

2. Create a small module for page range parsing and PDF splitting:

```python
"""Client-side PDF page extraction for --pages support."""

def parse_page_ranges(spec: str) -> list[tuple[int, int]]:
    """Parse '1-10,15,20-25' into [(0,9), (14,14), (19,24)] (0-indexed)."""
    ...

def extract_pages(src: Path, dest: Path, ranges: list[tuple[int, int]]) -> int:
    """Extract specified pages from src PDF, write to dest. Return page count."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise ImportError(
            "pypdf is required for --pages. Install it: pip install 'p2r[pages]'"
        )
    ...
```

Key design points:
- Lazy import of `pypdf` so the base install doesn't require it
- Clear error message if `pypdf` is not installed but `--pages` is used
- The split PDF is written to a temp file in the workdir, uploaded instead of the original
- Original filename is preserved in the API request (so MinerU names output correctly)

**File: `src/p2r/cli.py`**

3. Add `--pages` option to `convert`:

```python
@click.option("--pages", "page_spec", default=None,
              help="Page range to extract (e.g. '1-10', '1-5,10-15'). Requires pypdf.")
```

4. In `_run_convert_and_export()`, before calling `client.parse_pdf()`:

```python
if page_spec:
    from .pages import parse_page_ranges, extract_pages
    ranges = parse_page_ranges(page_spec)
    split_pdf = workdir / pdf_file.name  # same name for MinerU
    page_count = extract_pages(pdf_file, split_pdf, ranges)
    pdf_to_upload = split_pdf
    # Show info
    console.print(f"[bold]Pages:[/bold] {page_spec} ({page_count} pages extracted)")
else:
    pdf_to_upload = pdf_file
```

Then pass `pdf_to_upload` instead of `pdf_file` to `client.parse_pdf()`.

5. In `mineru.py`, `parse_pdf` already accepts `file_path: Path` — no changes needed there. But we need to ensure the upload uses the split file while the API request name uses the original filename. Looking at `request_upload_urls` (line 114): it uses `file_path.name`. Since we name the split file the same as the original, this works automatically.

### Phase 3: Structured Exit Codes

**File: `src/p2r/cli.py`**

1. Define exit code constants near the top of the file:

```python
EXIT_OK = 0
EXIT_GENERAL = 1
EXIT_CONFIG = 2
EXIT_API = 3
EXIT_EXPORT = 4
```

2. Update error handlers throughout `_run_convert_and_export()`:
   - Lines 341-352 (config/token errors): `sys.exit(EXIT_CONFIG)`
   - Lines 414-417 (MinerU API errors): `sys.exit(EXIT_API)`
   - Lines 495-498 (export errors): `sys.exit(EXIT_EXPORT)`

### Phase 4: Progress to stderr (for both modes)

**Rationale:** Even in human mode, progress should go to stderr so that future `--output -` (stdout) mode is possible. Rich Console supports `stderr=True`.

**File: `src/p2r/cli.py`**

1. Change the module-level console to use stderr for progress:

```python
# Progress/status messages go to stderr
_progress_console = Console(stderr=True)
# Final results go to stdout  
_result_console = Console()
```

2. Update all `console.print(...)` calls:
   - Progress messages, status updates, "Converting..." headers -> `_progress_console`
   - Final "Success! Exported files:" output -> `_result_console`
   - Error messages -> `_progress_console` (stderr is correct for errors)

This is a mild breaking change for humans who redirect stderr, but it's the correct Unix convention and enables composability.

---

## File Change Summary

| File | Change Type | Description |
|------|------------|-------------|
| `src/p2r/cli.py` | Modify | Add --json/--human/--pages flags, output mode logic, structured exit codes, stderr/stdout separation |
| `src/p2r/pages.py` | New | Page range parsing and PDF splitting with pypdf |
| `pyproject.toml` | Modify | Add `pypdf` as optional dependency under `[pages]` extra |
| `tests/test_json_output.py` | New | Test JSON output mode, TTY detection, error JSON |
| `tests/test_pages.py` | New | Test page range parsing, PDF splitting |

---

## Implementation Order

1. **Phase 3 first** (exit codes) — smallest change, no new dependencies, immediately useful
2. **Phase 4 next** (stderr separation) — prepares the ground for JSON mode
3. **Phase 1** (JSON output mode) — the main feature, builds on phases 3-4
4. **Phase 2 last** (page range) — independent feature, new dependency, can be a separate PR

---

## Risk Assessment

- **TTY auto-detection edge case:** CI environments, Docker containers, and `script` sessions may report TTY inconsistently. The `--json` / `--human` override flags mitigate this fully.
- **pypdf dependency size:** pypdf is pure Python, ~2MB, no C extensions. As an optional dep it adds zero weight to the base install.
- **MinerU API page naming:** When we upload a split PDF with the same filename, MinerU should name the output identically. If MinerU uses file hashes internally, this is fine. If it caches by name, re-uploading a different subset of the same file could hit stale cache. Low risk, testable.
- **Backward compatibility:** Human-mode output is unchanged. The only subtle change is progress moving to stderr (Phase 4), which won't affect typical terminal usage but could break scripts that parse stderr. Given that the current output is unparseable Rich markup, this is net positive.
