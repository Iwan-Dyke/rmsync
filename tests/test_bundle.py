"""Tests for rmsync.bundle."""

from __future__ import annotations

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
