"""Tests for rmsync.core orchestration and incremental logic."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from rmsync.core import _is_current, find_rmapi, render

_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"


def _write_bundle(path: Path, visible_name: str) -> None:
    """Write a minimal imported `.rmdoc` carrying an embedded PDF.

    Using the imported path exercises `render`'s folder-mirroring and
    incremental logic without depending on a parseable `.rm` stroke file;
    stroke rendering itself is covered by the Leadership behaviour test.
    """
    uuid = "11111111-1111-1111-1111-111111111111"
    path.parent.mkdir(parents=True, exist_ok=True)
    name = visible_name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{uuid}.content", '{"cPages": {"pages": []}}')
        zf.writestr(f"{uuid}.metadata", f'{{"visibleName": "{name}", "type": "DocumentType"}}')
        zf.writestr(f"{uuid}.pdf", _MINIMAL_PDF)


class TestFindRmapi:
    def test_errors_clearly_when_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rmsync.core.shutil.which", lambda _: None)
        monkeypatch.setattr("rmsync.core._RMAPI_FALLBACK", Path("/nonexistent/rmapi"))
        with pytest.raises(FileNotFoundError, match="rmapi not found"):
            find_rmapi()


class TestIsCurrent:
    def test_missing_output_is_not_current(self, tmp_path: Path) -> None:
        src = tmp_path / "a.rmdoc"
        src.write_text("x")
        assert _is_current(src, tmp_path / "a.pdf") is False

    def test_newer_output_is_current(self, tmp_path: Path) -> None:
        src = tmp_path / "a.rmdoc"
        src.write_text("x")
        out = tmp_path / "a.pdf"
        out.write_text("y")
        os.utime(out, (src.stat().st_mtime + 10, src.stat().st_mtime + 10))
        assert _is_current(src, out) is True


class TestRenderIncremental:
    def test_mirrors_folders_and_names_from_visible_name(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        output = tmp_path / "out"
        _write_bundle(source / "Work" / "deadbeef.rmdoc", "My Notebook")

        report = render(source, output)

        expected = output / "Work" / "My Notebook.pdf"
        assert expected.exists()
        assert report.rendered == [expected]

    def test_skips_unchanged_then_force_rerenders(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        output = tmp_path / "out"
        _write_bundle(source / "n.rmdoc", "N")

        first = render(source, output)
        assert len(first.rendered) == 1

        second = render(source, output)
        assert second.rendered == []
        assert len(second.skipped) == 1

        forced = render(source, output, force=True)
        assert len(forced.rendered) == 1
