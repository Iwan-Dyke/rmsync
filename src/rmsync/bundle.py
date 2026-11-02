"""Parse reMarkable `.rmdoc` ZIP bundles."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

_TOC_STEM = "toc"


@dataclass(frozen=True)
class Bundle:
    """A parsed `.rmdoc` bundle.

    `visible_name` names the notebook; `page_ids` is the ordered list of page
    uuids for a handwritten document; `embedded_pdf` is set only for imported
    documents that ship a `.pdf` inside the bundle.
    """

    path: Path
    uuid: str
    visible_name: str
    page_ids: list[str]
    embedded_pdf: str | None

    @property
    def is_imported(self) -> bool:
        """True when the bundle carries its own PDF and needs no rendering."""
        return self.embedded_pdf is not None


def read_bundle(path: Path) -> Bundle:
    """Read structure and metadata from a `.rmdoc` bundle without extracting it."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        content_name = _single_suffix(names, ".content", path)
        metadata_name = _single_suffix(names, ".metadata", path)
        uuid = content_name[: -len(".content")]

        content = json.loads(zf.read(content_name))
        metadata = json.loads(zf.read(metadata_name))

        embedded_pdf = f"{uuid}.pdf" if f"{uuid}.pdf" in names else None
        page_ids = [
            page["id"]
            for page in content.get("cPages", {}).get("pages", [])
            if page.get("id") != _TOC_STEM and not page.get("deleted")
        ]

    # A blank or whitespace-only visibleName must not yield an un-named or
    # hidden (".pdf" dotfile) output. Fall back to the bundle uuid.
    visible_name = metadata["visibleName"]
    if not visible_name.strip():
        visible_name = uuid

    return Bundle(
        path=path,
        uuid=uuid,
        visible_name=visible_name,
        page_ids=page_ids,
        embedded_pdf=embedded_pdf,
    )


def _single_suffix(names: list[str], suffix: str, path: Path) -> str:
    """Return the sole top-level entry ending in `suffix`."""
    matches = [n for n in names if n.endswith(suffix) and "/" not in n]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one '{suffix}' entry in {path}, found {matches}")
    return matches[0]
