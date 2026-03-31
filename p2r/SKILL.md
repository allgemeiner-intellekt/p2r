---
name: p2r
description: >
  Convert high-value PDFs to faithful Markdown using the p2r CLI (MinerU cloud API). This skill
  is for PDFs that you genuinely need to deeply understand — reference papers with mathematical
  models you want to build on, foundational papers whose equations and figures matter, technical
  specs with precise notation. Do NOT use this for casual "skim this PDF" or quick extraction
  tasks where the Read tool on the PDF directly would suffice. Use p2r when the PDF contains
  complex layout, math, tables, or figures that the basic Read tool would mangle, and the user
  needs high-fidelity conversion to work with the content seriously. Trigger when the user says
  things like "I need to deeply read this paper", "convert this reference paper", "p2r this",
  "extract the model from this PDF", "I want to work with the equations in this paper",
  "parse this paper so I can build on it".
---

## What this skill does

Converts a PDF file to high-fidelity Markdown via the `p2r` CLI, which uses the MinerU cloud
API. After conversion, reads the resulting Markdown file and brings its content into the
conversation so you can work with it deeply — reproduce equations, extend models, extract
precise data, etc.

## When to use this vs. just reading the PDF

p2r calls a cloud API and takes 30-120 seconds. Only use it when the fidelity matters:

- **Use p2r:** Reference papers with math/equations you need to reproduce, papers with complex
  tables or figures, foundational papers the user wants to build on or extend, any PDF where
  layout-aware extraction matters.
- **Don't use p2r:** Quick lookups ("what's the conclusion of this paper?"), simple text-heavy
  PDFs without complex layout, casual skimming. For these, just use the Read tool directly on
  the PDF — it's instant and good enough.

## Prerequisites

- `p2r` is installed and on PATH
- The user has a MinerU API token configured
- The `agent` profile exists in `~/.p2r_config.json` (exports markdown to `./md`, keeps images
  in `./md/image`, no HTML, no image upload)

## Invocation

Always use the `agent` profile and `--json` flag:

```bash
p2r <pdf_path> -p agent --json
```

This sends all progress/status output to stderr (invisible to tool output) and prints a single
JSON object to stdout.

## JSON output

**Success:**
```json
{"success": true, "markdown_path": "/absolute/path/paper.md"}
```

**Error:**
```json
{"success": false, "error": "description of what went wrong", "exit_code": 3}
```

**Image upload fallback** (unlikely with agent profile, but possible):
```json
{"success": true, "markdown_path": "/absolute/path/paper.md", "warning": "Image upload failed; raw output preserved"}
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Config error (missing token, unknown profile) |
| 3 | MinerU API error (upload failed, timeout, server error) |
| 4 | Export error (couldn't write output files) |

## Output path

The converted Markdown is written under `<cwd>/md/`. The exact subdirectory name includes a
model-version suffix appended by the CLI (e.g. `_v2` for the default `vlm` model):

```
<cwd>/md/<pdf_stem>_v2/<pdf_stem>.md   # typical with default --model vlm
<cwd>/md/<pdf_stem>/<pdf_stem>.md      # pipeline model or older CLI versions
```

The JSON output always contains the exact `markdown_path` — use that, don't guess. Images are
placed in `<cwd>/md/image/`. Image references in the Markdown (`![...](image/...)`) point to
that directory — note their content in your response where figures are meaningful (e.g., "Figure
3 shows a diagram of X"); skip decorative ones.

## Workflow

1. **Validate the PDF path.** Make sure the file exists and ends with `.pdf`. If the user gave a
   relative path, resolve it. If they said something vague like "this paper" without a path, ask
   which file they mean.

2. **Check the cache.** Glob for `<cwd>/md/<pdf_stem>*/<pdf_stem>.md`. If a match exists, skip
   the API call entirely and use that file — no need to re-convert.

3. **Run p2r.** Execute:
   ```bash
   p2r <pdf_path> -p agent --json
   ```
   Use a generous timeout (5 minutes / 300000ms) — MinerU cloud processing can take a while for
   large PDFs.

4. **Parse the result.** The stdout is a JSON object. Parse it:
   - If `success` is `true`, read the file at `markdown_path`.
   - If `success` is `false`, report the error to the user with the specific exit code context
     (e.g., exit code 2 means their config is wrong, exit code 3 means the API had an issue).

5. **Read the Markdown.** The converted file has proper section headers throughout. For targeted
   requests ("find the section on X", "extract the model from section 3"), use Grep on the
   Markdown file first to locate the relevant line range, then read only that range — much faster
   than reading linearly from the top. For open-ended requests (summarize, explain), read the
   full file; if it's very long (>2000 lines), read in chunks and let the user know the full file
   is at the path.

6. **Proceed with the user's actual request.** The conversion is usually a means to an end — the
   user wants to read, summarize, search, or otherwise work with the paper's content. Use the
   Markdown content to fulfill their original ask.

## Error handling

- **Exit code 2 (config):** Tell the user their p2r config needs attention. Suggest running
  `p2r init` or checking `~/.p2r_config.json` for a valid API token and `agent` profile.
- **Exit code 3 (API):** The MinerU service had an issue. Suggest retrying in a minute, or
  checking if their API token is valid.
- **Exit code 4 (export):** File system issue writing outputs. Check disk space and permissions.
- **Command not found:** Tell the user to install p2r (`uv tool install p2r` or `pipx install p2r`).

## Example

User: "read this paper and summarize it: ~/Downloads/attention.pdf"

1. Glob `<cwd>/md/attention*` — no match, so proceed with conversion.
2. Run `p2r ~/Downloads/attention.pdf -p agent --json` (timeout 300s)
3. Parse JSON → `markdown_path` is `<cwd>/md/attention_v2/attention.md`
4. Read `<cwd>/md/attention_v2/attention.md`
5. Summarize the content for the user
