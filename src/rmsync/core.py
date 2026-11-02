"""Pull and render orchestration."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .bundle import Bundle, read_bundle
from .render import render_bundle

DEFAULT_SOURCE = Path.home() / "org" / "remarkable"
DEFAULT_OUTPUT = Path.home() / "org" / "remarkable-pdf"
_RMAPI_FALLBACK = Path.home() / "go" / "bin" / "rmapi"


@dataclass
class RenderReport:
    """Outcome of a render pass."""

    rendered: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    trashed: list[Path] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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


def render(
    source: Path, output: Path, *, force: bool = False, include_trash: bool = False
) -> RenderReport:
    """Render changed `.rmdoc` bundles under `source`, mirroring folders into `output`.

    Bundles under a top-level ``trash/`` directory are skipped unless
    ``include_trash`` is set: reMarkable stores deleted notebooks there, and we
    do not render deleted work by default.
    """
    report = RenderReport()
    # Track output filenames already claimed per directory within this pass so
    # two bundles that resolve to the same name do not silently overwrite.
    claimed: dict[Path, set[str]] = {}
    for bundle_path in sorted(source.rglob("*.rmdoc")):
        rel_dir = bundle_path.parent.relative_to(source)
        if not include_trash and _is_trashed(rel_dir):
            report.trashed.append(bundle_path)
            continue
        try:
            bundle = read_bundle(bundle_path)
            out_dir = output / rel_dir
            filename = _unique_filename(bundle, out_dir, claimed, report)
            out_path = out_dir / filename
            if not force and _is_current(bundle_path, out_path):
                report.skipped.append(out_path)
                continue
            render_bundle(bundle, out_path)
            report.rendered.append(out_path)
        except Exception as exc:  # noqa: BLE001 — per-bundle boundary: record and continue
            report.failed.append((bundle_path, f"{type(exc).__name__}: {exc}"))
    return report


def sync(
    source: Path, output: Path, *, force: bool = False, include_trash: bool = False
) -> RenderReport:
    """Run `pull` then `render`."""
    pull(source)
    return render(source, output, force=force, include_trash=include_trash)


def _is_trashed(rel_dir: Path) -> bool:
    """True when `rel_dir` is the top-level `trash/` directory or beneath it."""
    return rel_dir == Path("trash") or rel_dir.parts[:1] == ("trash",)


def _unique_filename(
    bundle: Bundle, out_dir: Path, claimed: dict[Path, set[str]], report: RenderReport
) -> str:
    """Return a PDF filename for `bundle`, disambiguating collisions in `out_dir`.

    Two bundles in the same output directory that share a visibleName would map
    to the same path and silently overwrite one another. When that happens, we
    append a short uuid-derived suffix (e.g. ``Name (ab12cd).pdf``) so both are
    preserved, and record a warning.
    """
    seen = claimed.setdefault(out_dir, set())
    base = f"{bundle.visible_name}.pdf"
    if base not in seen:
        seen.add(base)
        return base
    disambiguated = f"{bundle.visible_name} ({bundle.uuid[:6]}).pdf"
    seen.add(disambiguated)
    report.warnings.append(
        f"name collision in {out_dir}: '{base}' already taken; "
        f"writing '{disambiguated}' instead (uuid {bundle.uuid})"
    )
    return disambiguated


def _is_current(bundle_path: Path, out_path: Path) -> bool:
    """True when `out_path` exists and is at least as new as its source bundle."""
    return out_path.exists() and out_path.stat().st_mtime >= bundle_path.stat().st_mtime
