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
  notebooks, e.g. the "Leadership" notebook).
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
