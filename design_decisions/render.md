# ADR: Rendering `.rmdoc` bundles to PDF

Status: Accepted

## Context

reMarkable notebooks arrive as `.rmdoc` ZIP bundles. A handwritten notebook
holds one binary v6 `.rm` stroke file per page, with page order recorded in a
`<uuid>.content` JSON (`cPages.pages[].id`). Imported documents additionally
ship an embedded `.epub` and/or `.pdf`. We need one readable, rasterizable PDF
per notebook, produced by an installable CLI, with no heavyweight native
dependencies to manage on each machine.

Several forces shaped the design:

- `rmc` can parse v6 strokes and render SVG, but its built-in `-t pdf` shells
  out to **Inkscape**, which is not installed and is a heavy dependency.
- `rmc` 0.3.0 crashes with a `KeyError` when a stroke references a colour id
  newer than its built-in palette knows (observed with colour id 9 in real
  notebooks).
- Imported documents already contain a perfectly good PDF.

## Decision

**SVG-intermediate, pure-Python pipeline.** For handwritten pages, call `rmc`'s
library functions in-process to render each `.rm` page to SVG, convert each SVG
to PDF with `cairosvg`, and merge the per-page PDFs with `pypdf`. `cairosvg` is
pure Python, so we avoid Inkscape and poppler entirely and keep the tool
`uv tool install`-able with no system packages.

**Palette shim applied in-process.** We subclass `rmc`'s palette dict so missing
colour ids fall back to black, and patch it onto the `writing_tools.RM_PALETTE`
module global that `rmc`'s `Pen` looks up at render time:

```python
class _SafePalette(dict):
    def __missing__(self, key):
        return (0, 0, 0)


wt.RM_PALETTE = _SafePalette(wt.RM_PALETTE)
```

Calling `rmc` in-process (rather than shelling out) makes the shim reliable:
the patched global is guaranteed to be the one the renderer reads. Black is a
safe fallback — an unknown colour renders as a visible stroke rather than
crashing the whole notebook.

**Imported documents emit their embedded PDF directly.** When a bundle contains
`<uuid>.pdf`, we write that PDF out unchanged and skip rendering. Rendering
annotation `.rm` layers on top of an imported PDF is out of scope for v1.

**`pypdf` for the merge.** It is pure Python and already in the dependency set
conceptually; `pymupdf` would also work but pulls a larger native wheel and
offers nothing we need here, so `pypdf` wins on minimalism.

## Consequences

- No Inkscape, no poppler — the tool installs and runs with only Python wheels.
- Unknown future colour ids degrade gracefully to black instead of crashing.
- Annotations over imported PDFs are not rendered in v1; the embedded PDF is
  emitted as-is. This is a known, documented limitation.
- We depend on `rmc`'s internal `svg` and `writing_tools` modules, not just its
  CLI. If `rmc` restructures those internals, the shim and the in-process call
  may need revisiting — an accepted trade-off for a reliable palette fix.

## Deleted pages and per-bundle resilience

**Deleted pages are not listed.** A page entry in `cPages.pages[]` can carry a
truthy `deleted` object (live pages carry `deleted: null`). A deleted page has
no `<uuid>/<page_id>.rm` file in the archive, so including it crashed rendering
with a `KeyError`. `read_bundle` now excludes any page with a truthy `deleted`
value when building `page_ids`, alongside the existing `toc` skip. A notebook
therefore renders only its live pages (e.g. 16 declared, 1 deleted, 15
rendered).

**A listed-but-absent `.rm` is a hard error, not a silent skip.** If, after
excluding deleted pages, a listed page's stroke file is still missing, the
bundle is genuinely malformed; rendering raises a clear error naming the bundle
and page rather than skipping silently (team standard: no silent failures).

**One bad bundle no longer aborts the whole run.** `core.render` catches render
failures at the per-bundle boundary, records each as `(path, message)` in
`RenderReport.failed`, and continues with the rest. The CLI reports
`N rendered, M unchanged, K failed` and lists each failure. The catch is scoped
to the per-bundle loop body only — we keep the error message and surface it
rather than swallowing exceptions we cannot describe.

## Trash exclusion, blank-name fallback, and collision disambiguation

A UAT run over the full real notebook set surfaced three defects, fixed here.

**Trashed notebooks are not rendered by default.** `rmapi mget / ` pulls the
reMarkable **trash** folder, so deleted bundles land under a top-level
`trash/` directory of the source. `core.render` now skips any bundle whose
path is under `trash/` and counts them separately (`RenderReport.trashed`,
surfaced as `trashed-skipped` in the CLI summary, distinct from `unchanged`). A
`--include-trash` flag (default off) overrides this when deleted work really
does need rendering. Skipping on the `trash/` path — rather than the
`parent: "trash"` metadata signal, which would also work — is the simplest
check and avoids pulling/parsing cost.

**A blank visibleName falls back to the uuid.** One trashed bundle carried
`visibleName: ""`, which produced an output file literally named `.pdf` — a
hidden dotfile. `read_bundle` now substitutes the bundle uuid whenever
`visibleName` is empty or whitespace-only, so every notebook has a visible,
named output (`<uuid>.pdf`) and no silent blank names are possible.

**Name collisions are disambiguated, never overwritten.** Two notebooks sharing
a `visibleName` in the same folder would map to the same output path and one
would silently overwrite the other — latent data loss (zero collisions in the
current data, but a real bug). `core.render` tracks the output names already
claimed per directory within a pass; on a collision it appends a short
uuid-derived suffix (`Name (ab12cd).pdf`) and records a warning in
`RenderReport.warnings`, which the CLI prints. Both notebooks are preserved.
