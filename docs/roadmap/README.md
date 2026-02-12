# p2r Implementation Roadmap (Ordered by Dependencies)

This folder breaks the plan into small, dependency-ordered features. Implement them in numeric order.

## Dependency Map (Why This Order)

1. **Config v2 + profiles** is the foundation for all later behavior (default_profile, export dirs, keep flags).
2. **New CLI surface** (`p2r PDF_FILE`, `--profile`, new export options) must exist before we can wire behavior.
3. **Workdir + export routing** is the core user-facing behavior (md/html placement, output semantics).
4. **Keep assets + bundling rules** builds on export routing to avoid broken relative links.
5. **Image upload integration + failure fallback** depends on both export routing and existing image_upload module.
6. **`p2r config` command** depends on config v2 (editor setting) and is independent of export internals.
7. **Tests + README updates** should land after behaviors stabilize (but you can add tests per-step if you prefer).

## Files / Docs

- `docs/roadmap/01-config-v2-profiles.md`
- `docs/roadmap/02-cli-new-surface.md`
- `docs/roadmap/03-workdir-and-export.md`
- `docs/roadmap/04-asset-keeping-bundling.md`
- `docs/roadmap/05-image-upload-and-fallback.md`
- `docs/roadmap/06-p2r-config-command.md`
- `docs/roadmap/07-tests-and-docs.md`

