"""Tests for rmsync.bundle."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from rmsync.bundle import read_bundle

FIXTURE = Path("/Users/Iwan.Dyke/org/remarkable/2. Work/Leadership.rmdoc")


@pytest.mark.skipif(not FIXTURE.exists(), reason="Leadership fixture not available")
class TestReadBundle:
    def test_reads_visible_name(self) -> None:
        assert read_bundle(FIXTURE).visible_name == "Leadership"

    def test_orders_ten_pages(self) -> None:
        assert len(read_bundle(FIXTURE).page_ids) == 10

    def test_excludes_toc(self) -> None:
        assert "toc" not in read_bundle(FIXTURE).page_ids

    def test_handwritten_is_not_imported(self) -> None:
        bundle = read_bundle(FIXTURE)
        assert bundle.is_imported is False
        assert bundle.embedded_pdf is None


class TestDeletedPages:
    """A page marked deleted has no `.rm` file and must not be listed."""

    def _write_bundle(self, path: Path) -> tuple[str, str]:
        """Write a handwritten bundle with one normal and one deleted page.

        Mirrors the real JSON shape: live pages carry ``deleted: null`` while a
        deleted page carries a ``deleted`` object. Only the live page's `.rm`
        file is written, matching a real archive.
        """
        uuid = "22222222-2222-2222-2222-222222222222"
        live_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        dead_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        content = {
            "cPages": {
                "pages": [
                    {"id": live_id, "deleted": None},
                    {"id": dead_id, "deleted": {"timestamp": "1:1", "value": 1}},
                ]
            }
        }
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(f"{uuid}.content", json.dumps(content))
            zf.writestr(f"{uuid}.metadata", '{"visibleName": "Matrix", "type": "DocumentType"}')
            zf.writestr(f"{uuid}/{live_id}.rm", b"stroke-bytes")
        return live_id, dead_id

    def test_excludes_deleted_page_id(self, tmp_path: Path) -> None:
        path = tmp_path / "matrix.rmdoc"
        live_id, dead_id = self._write_bundle(path)

        bundle = read_bundle(path)

        assert bundle.page_ids == [live_id]
        assert dead_id not in bundle.page_ids
