"""Render `.rmdoc` bundles to PDF.

Handwritten pages go through the proven chain: `rmc` renders each v6 `.rm`
stroke file to SVG in-process, `cairosvg` converts SVG to PDF, and `pypdf`
merges the pages. Imported documents emit their embedded PDF directly.

No Inkscape or poppler: `cairosvg` is pure Python, so `rmc`'s Inkscape-backed
`-t pdf` path is deliberately avoided.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import cairosvg
from pypdf import PdfReader, PdfWriter

# CRITICAL palette shim. rmc 0.3.0 crashes with KeyError on newer colour ids
# (e.g. id 9). Subclass the palette dict so missing keys fall back to black,
# then patch it onto the module global that `Pen` looks up at render time.
from rmc.exporters import writing_tools as _wt

from .bundle import Bundle


class _SafePalette(dict):
    def __missing__(self, key: int) -> tuple[int, int, int]:
        return (0, 0, 0)


_wt.RM_PALETTE = _SafePalette(_wt.RM_PALETTE)

from rmc.exporters import svg as _svg


def render_bundle(bundle: Bundle, out_path: Path) -> None:
    """Render `bundle` to a single PDF at `out_path`."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if bundle.is_imported:
        _emit_embedded_pdf(bundle, out_path)
    else:
        _render_handwritten(bundle, out_path)


def _emit_embedded_pdf(bundle: Bundle, out_path: Path) -> None:
    """Write the imported document's embedded PDF straight to `out_path`.

    Annotation layers over an imported PDF are out of scope for v1.
    """
    assert bundle.embedded_pdf is not None
    with zipfile.ZipFile(bundle.path) as zf:
        out_path.write_bytes(zf.read(bundle.embedded_pdf))


def _render_handwritten(bundle: Bundle, out_path: Path) -> None:
    """Render each page to SVG, convert to PDF, and merge into one PDF."""
    writer = PdfWriter()
    with zipfile.ZipFile(bundle.path) as zf:
        for page_id in bundle.page_ids:
            rm_bytes = zf.read(f"{bundle.uuid}/{page_id}.rm")
            svg_text = _rm_to_svg(rm_bytes)
            pdf_bytes = cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"))
            writer.append(PdfReader(io.BytesIO(pdf_bytes)))
    with out_path.open("wb") as f:
        writer.write(f)


def _rm_to_svg(rm_bytes: bytes) -> str:
    """Convert one v6 `.rm` stroke file to an SVG string (in-process)."""
    tree = _svg.read_tree(io.BytesIO(rm_bytes))
    out = io.StringIO()
    _svg.tree_to_svg(tree, out)
    return out.getvalue()
