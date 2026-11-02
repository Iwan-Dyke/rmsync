"""Tests for rmsync.render, including an end-to-end behaviour test."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from pypdf import PdfReader

from rmsync.bundle import read_bundle
from rmsync.render import _SafePalette, render_bundle

FIXTURE = Path("/Users/Iwan.Dyke/org/remarkable/2. Work/Leadership.rmdoc")


class TestSafePalette:
    def test_missing_colour_id_falls_back_to_black(self) -> None:
        palette = _SafePalette({0: (255, 255, 255)})
        assert palette[9] == (0, 0, 0)

    def test_known_colour_id_unchanged(self) -> None:
        palette = _SafePalette({0: (255, 255, 255)})
        assert palette[0] == (255, 255, 255)


@pytest.mark.skipif(not FIXTURE.exists(), reason="Leadership fixture not available")
class TestRenderLeadershipFixture:
    """End-to-end: the proven chain must yield a valid, non-blank PDF."""

    def test_produces_valid_multipage_pdf_with_strokes(self, tmp_path: Path) -> None:
        out = tmp_path / "Leadership.pdf"
        render_bundle(read_bundle(FIXTURE), out)

        assert out.stat().st_size > 0
        assert len(PdfReader(str(out)).pages) == 10

        page = pdfium.PdfDocument(str(out))[0]
        grey = page.render(scale=1.5).to_pil().convert("L")
        dark_pixels = sum(grey.histogram()[:128])
        assert dark_pixels > 500, "page 1 appears blank"


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
