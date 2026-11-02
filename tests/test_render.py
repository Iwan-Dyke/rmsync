"""Tests for rmsync.render, including an end-to-end behaviour test."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from pypdf import PdfReader
from rmscene import simple_text_document, write_blocks

from rmsync.bundle import read_bundle
from rmsync.render import _SafePalette, render_bundle


def _write_handwritten_bundle(path: Path, visible_name: str, lines: list[str]) -> None:
    """Write a handwritten `.rmdoc` with one real v6 `.rm` page per line.

    The `.rm` stroke files are synthesised with `rmscene` (the same format
    `rmc` reads), so this exercises the full handwritten chain
    (`rmc` -> SVG -> cairosvg -> pypdf) in-process with no external fixture.
    """
    uuid = "55555555-5555-5555-5555-555555555555"
    page_ids = [f"{i:08d}-aaaa-aaaa-aaaa-aaaaaaaaaaaa" for i in range(len(lines))]
    content = {"cPages": {"pages": [{"id": pid, "deleted": None} for pid in page_ids]}}
    metadata = {"visibleName": visible_name, "type": "DocumentType"}
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{uuid}.content", json.dumps(content))
        zf.writestr(f"{uuid}.metadata", json.dumps(metadata))
        for pid, line in zip(page_ids, lines):
            buf = io.BytesIO()
            write_blocks(buf, simple_text_document(line))
            zf.writestr(f"{uuid}/{pid}.rm", buf.getvalue())


class TestSafePalette:
    def test_missing_colour_id_falls_back_to_black(self) -> None:
        palette = _SafePalette({0: (255, 255, 255)})
        assert palette[9] == (0, 0, 0)

    def test_known_colour_id_unchanged(self) -> None:
        palette = _SafePalette({0: (255, 255, 255)})
        assert palette[0] == (255, 255, 255)


class TestRenderHandwritten:
    """End-to-end: the proven chain must yield a valid, non-blank PDF."""

    def test_produces_valid_multipage_pdf_with_strokes(self, tmp_path: Path) -> None:
        bundle_path = tmp_path / "notebook.rmdoc"
        _write_handwritten_bundle(bundle_path, "Notebook", ["page one", "page two", "page three"])

        out = tmp_path / "Notebook.pdf"
        render_bundle(read_bundle(bundle_path), out)

        assert out.stat().st_size > 0
        assert len(PdfReader(str(out)).pages) == 3

        page = pdfium.PdfDocument(str(out))[0]
        grey = page.render(scale=1.5).to_pil().convert("L")
        dark_pixels = sum(grey.histogram()[:128])
        assert dark_pixels > 0, "page 1 appears blank"

    def test_missing_stroke_file_is_a_hard_error(self, tmp_path: Path) -> None:
        """A listed page with no `.rm` file in the archive must raise clearly."""
        uuid = "66666666-6666-6666-6666-666666666666"
        page_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        bundle_path = tmp_path / "broken.rmdoc"
        content = {"cPages": {"pages": [{"id": page_id, "deleted": None}]}}
        with zipfile.ZipFile(bundle_path, "w") as zf:
            zf.writestr(f"{uuid}.content", json.dumps(content))
            zf.writestr(f"{uuid}.metadata", '{"visibleName": "Broken", "type": "DocumentType"}')

        with pytest.raises(ValueError, match="malformed bundle"):
            render_bundle(read_bundle(bundle_path), tmp_path / "Broken.pdf")


class TestRenderImported:
    def test_emits_embedded_pdf_unchanged(self, tmp_path: Path) -> None:
        pdf_bytes = b"%PDF-1.4\nimported-content\n%%EOF\n"
        bundle_path = tmp_path / "imported.rmdoc"
        uuid = "33333333-3333-3333-3333-333333333333"
        with zipfile.ZipFile(bundle_path, "w") as zf:
            zf.writestr(f"{uuid}.content", '{"cPages": {"pages": []}}')
            zf.writestr(f"{uuid}.metadata", '{"visibleName": "Doc", "type": "DocumentType"}')
            zf.writestr(f"{uuid}.pdf", pdf_bytes)

        bundle = read_bundle(bundle_path)
        assert bundle.is_imported is True

        out = tmp_path / "Doc.pdf"
        render_bundle(bundle, out)
        assert out.read_bytes() == pdf_bytes
