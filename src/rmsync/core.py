"""Pull and render orchestration."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .bundle import read_bundle
from .render import render_bundle

DEFAULT_SOURCE = Path.home() / "org" / "remarkable"
DEFAULT_OUTPUT = Path.home() / "org" / "remarkable-pdf"
_RMAPI_FALLBACK = Path.home() / "go" / "bin" / "rmapi"


@dataclass
class RenderReport:
    """Outcome of a render pass."""

    rendered: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)


def find_rmapi() -> Path:
    """Locate the external `rmapi` binary on PATH or at its known install path."""
    found = shutil.which("rmapi")
    if found:
        return Path(found)
    if _RMAPI_FALLBACK.is_file():
        return _RMAPI_FALLBACK
    raise FileNotFoundError(
        "rmapi not found on PATH or at ~/go/bin/rmapi. Install and authenticate it first."
    )


def pull(source: Path) -> None:
    """Incrementally download changed notebooks, pruning cloud deletions."""
    rmapi = find_rmapi()
    source.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(rmapi), "mget", "-i", "-d", "-o", str(source), "/"], check=True)


def render(source: Path, output: Path, *, force: bool = False) -> RenderReport:
    """Render changed `.rmdoc` bundles under `source`, mirroring folders into `output`."""
    report = RenderReport()
    for bundle_path in sorted(source.rglob("*.rmdoc")):
        rel_dir = bundle_path.parent.relative_to(source)
        bundle = read_bundle(bundle_path)
        out_path = output / rel_dir / f"{bundle.visible_name}.pdf"
        if not force and _is_current(bundle_path, out_path):
            report.skipped.append(out_path)
            continue
        render_bundle(bundle, out_path)
        report.rendered.append(out_path)
    return report


def sync(source: Path, output: Path, *, force: bool = False) -> RenderReport:
    """Run `pull` then `render`."""
    pull(source)
    return render(source, output, force=force)


def _is_current(bundle_path: Path, out_path: Path) -> bool:
    """True when `out_path` exists and is at least as new as its source bundle."""
    return out_path.exists() and out_path.stat().st_mtime >= bundle_path.stat().st_mtime
