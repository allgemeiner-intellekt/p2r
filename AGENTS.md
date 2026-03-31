# Overview

p2r is a Python CLI that sends a PDF to the MinerU cloud API and exports Markdown/HTML.

## Agent usage

p2r is designed to be used by AI agents and scripts. Key features:

- All Rich/decorative output goes to **stderr**; stdout is clean for piping
- `--json` flag emits a single JSON object to stdout on completion
- Structured exit codes: `0` OK, `2` config error, `3` API error, `4` export error

### Recommended invocation

```bash
p2r paper.pdf --json 2>/dev/null
```

Returns:
```json
{"success": true, "markdown_path": "/absolute/path/paper.md", "html_path": "/absolute/path/paper.html"}
```

On error:
```json
{"success": false, "error": "...", "exit_code": 3}
```

### Get just the markdown path

```bash
p2r paper.pdf --json 2>/dev/null | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['markdown_path'])"
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General/unknown error |
| 2 | Config error (missing token, unknown profile) |
| 3 | MinerU API error |
| 4 | Export error |

## Claude Code skill

A ready-to-use Claude Code skill is bundled at `p2r/SKILL.md`. Copy or symlink it to
`~/.claude/skills/p2r` to enable automatic p2r usage in Claude Code sessions. See the
README for setup instructions.

## Source layout

```
src/p2r/
├── cli.py          # CLI commands, progress bars, --json flag
├── mineru.py       # MinerU API client
├── export.py       # File export logic
├── config.py       # Config loading/saving
└── image_upload.py # Image upload + markdown rewriting
p2r/
└── SKILL.md        # Claude Code skill definition
```
