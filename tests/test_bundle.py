"""Tests for rmsync.bundle."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from rmscene import simple_text_document, write_blocks

from rmsync.bundle import read_bundle


class TestReadBundle:
    """Reading structure and metadata from a handwritten bundle."""

    def _write_bundle(self, path: Path, visible_name: str, page_count: int) -> list[str]:
        """Write a handwritten bundle with `page_count` real v6 `.rm` pages.

        A `toc` entry is included in the page list to prove it is excluded.
        """
        uuid = "77777777-7777-7777-7777-777777777777"
        page_ids = [f"{i:08d}-aaaa-aaaa-aaaa-aaaaaaaaaaaa" for i in range(page_count)]
        pages = [{"id": "toc", "deleted": None}]
        pages += [{"id": pid, "deleted": None} for pid in page_ids]
        content = {"cPages": {"pages": pages}}
        metadata = {"visibleName": visible_name, "type": "DocumentType"}
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(f"{uuid}.content", json.dumps(content))
            zf.writestr(f"{uuid}.metadata", json.dumps(metadata))
            for pid in page_ids:
                buf = io.BytesIO()
                write_blocks(buf, simple_text_document("stroke"))
                zf.writestr(f"{uuid}/{pid}.rm", buf.getvalue())
        return page_ids

    def test_reads_visible_name(self, tmp_path: Path) -> None:
        path = tmp_path / "n.rmdoc"
        self._write_bundle(path, "My Notebook", page_count=3)
        assert read_bundle(path).visible_name == "My Notebook"

    def test_orders_pages(self, tmp_path: Path) -> None:
        path = tmp_path / "n.rmdoc"
        page_ids = self._write_bundle(path, "My Notebook", page_count=3)
        assert read_bundle(path).page_ids == page_ids

    def test_excludes_toc(self, tmp_path: Path) -> None:
        path = tmp_path / "n.rmdoc"
        self._write_bundle(path, "My Notebook", page_count=3)
        assert "toc" not in read_bundle(path).page_ids

    def test_handwritten_is_not_imported(self, tmp_path: Path) -> None:
        path = tmp_path / "n.rmdoc"
        self._write_bundle(path, "My Notebook", page_count=1)
        bundle = read_bundle(path)
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
            zf.writestr(f"{uuid}.metadata", '{"visibleName": "Notes", "type": "DocumentType"}')
            zf.writestr(f"{uuid}/{live_id}.rm", b"stroke-bytes")
        return live_id, dead_id

    def test_excludes_deleted_page_id(self, tmp_path: Path) -> None:
        path = tmp_path / "notes.rmdoc"
        live_id, dead_id = self._write_bundle(path)

        bundle = read_bundle(path)

        assert bundle.page_ids == [live_id]
        assert dead_id not in bundle.page_ids


class TestBlankVisibleName:
    """A blank or whitespace-only visibleName must fall back to the uuid."""

    def _write_bundle(self, path: Path, visible_name: str) -> str:
        uuid = "44444444-4444-4444-4444-444444444444"
        content = {"cPages": {"pages": []}}
        metadata = {"visibleName": visible_name, "type": "DocumentType"}
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(f"{uuid}.content", json.dumps(content))
            zf.writestr(f"{uuid}.metadata", json.dumps(metadata))
        return uuid

    def test_empty_name_falls_back_to_uuid(self, tmp_path: Path) -> None:
        path = tmp_path / "blank.rmdoc"
        uuid = self._write_bundle(path, "")

        assert read_bundle(path).visible_name == uuid

    def test_whitespace_name_falls_back_to_uuid(self, tmp_path: Path) -> None:
        path = tmp_path / "ws.rmdoc"
        uuid = self._write_bundle(path, "   ")

        assert read_bundle(path).visible_name == uuid

    def test_normal_name_unchanged(self, tmp_path: Path) -> None:
        path = tmp_path / "named.rmdoc"
        self._write_bundle(path, "Real Name")

        assert read_bundle(path).visible_name == "Real Name"
