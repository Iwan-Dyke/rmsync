"""Tests for rmsync.core orchestration and incremental logic."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from rmsync.core import _is_current, find_rmapi, render

_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"


def _write_bundle(path: Path, visible_name: str, uuid: str | None = None) -> None:
    """Write a minimal imported `.rmdoc` carrying an embedded PDF.

    Using the imported path exercises `render`'s folder-mirroring and
    incremental logic without depending on a parseable `.rm` stroke file;
    stroke rendering itself is covered by the Leadership behaviour test.
    """
    if uuid is None:
        uuid = "11111111-1111-1111-1111-111111111111"
    path.parent.mkdir(parents=True, exist_ok=True)
    name = visible_name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{uuid}.content", '{"cPages": {"pages": []}}')
        zf.writestr(f"{uuid}.metadata", f'{{"visibleName": "{name}", "type": "DocumentType"}}')
        zf.writestr(f"{uuid}.pdf", _MINIMAL_PDF)


def _write_malformed_bundle(path: Path, visible_name: str) -> None:
    """Write a handwritten `.rmdoc` that lists a page with no stroke file.

    This is a genuinely malformed archive: `render_bundle` raises when the
    listed `.rm` is absent, letting us prove one bad bundle does not abort
    the whole run.
    """
    uuid = "33333333-3333-3333-3333-333333333333"
    missing_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f'{{"cPages": {{"pages": [{{"id": "{missing_id}", "deleted": null}}]}}}}'
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{uuid}.content", content)
        zf.writestr(f"{uuid}.metadata", f'{{"visibleName": "{visible_name}", "type": "DocumentType"}}')


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


class TestRenderResilience:
    """One unrenderable bundle must not abort the whole run."""

    def test_one_failure_does_not_abort_run(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        output = tmp_path / "out"
        _write_bundle(source / "good.rmdoc", "Good")
        _write_malformed_bundle(source / "bad.rmdoc", "Bad")

        report = render(source, output)

        assert report.rendered == [output / "Good.pdf"]
        assert (output / "Good.pdf").exists()
        assert len(report.failed) == 1
        failed_path, error = report.failed[0]
        assert failed_path == source / "bad.rmdoc"
        assert "malformed bundle" in error


class TestRenderTrash:
    """Bundles under a top-level `trash/` dir are skipped unless opted in."""

    def test_trashed_bundle_skipped_by_default(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        output = tmp_path / "out"
        _write_bundle(source / "trash" / "deleted.rmdoc", "Deleted Note")
        _write_bundle(source / "Work" / "live.rmdoc", "Live Note")

        report = render(source, output)

        assert report.rendered == [output / "Work" / "Live Note.pdf"]
        assert report.trashed == [source / "trash" / "deleted.rmdoc"]
        assert not (output / "trash" / "Deleted Note.pdf").exists()

    def test_trashed_bundle_rendered_when_included(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        output = tmp_path / "out"
        _write_bundle(source / "trash" / "deleted.rmdoc", "Deleted Note")

        report = render(source, output, include_trash=True)

        assert (output / "trash" / "Deleted Note.pdf").exists()
        assert report.trashed == []
        assert output / "trash" / "Deleted Note.pdf" in report.rendered


class TestRenderNameCollision:
    """Two bundles that resolve to the same output name must not overwrite."""

    def test_colliding_names_both_rendered_distinctly(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        output = tmp_path / "out"
        uuid_a = "aaaaaaaa-1111-1111-1111-111111111111"
        uuid_b = "bbbbbbbb-2222-2222-2222-222222222222"
        _write_bundle(source / "Work" / "a.rmdoc", "Notes", uuid=uuid_a)
        _write_bundle(source / "Work" / "b.rmdoc", "Notes", uuid=uuid_b)

        report = render(source, output)

        assert len(report.rendered) == 2
        assert len({p.name for p in report.rendered}) == 2
        for path in report.rendered:
            assert path.exists()
        assert len(report.warnings) == 1
        assert "collision" in report.warnings[0]
