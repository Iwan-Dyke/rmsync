"""Command-line entry point for rmsync."""

from __future__ import annotations

import argparse
from pathlib import Path

from .core import DEFAULT_OUTPUT, DEFAULT_SOURCE, RenderReport, pull, render, sync


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the requested command."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "pull":
        pull(args.source)
        print(f"Pulled notebooks into {args.source}")
    elif args.command == "render":
        _print_report(
            render(args.source, args.output, force=args.force, include_trash=args.include_trash)
        )
    elif args.command == "sync":
        _print_report(
            sync(args.source, args.output, force=args.force, include_trash=args.include_trash)
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rmsync", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    pull_p = sub.add_parser("pull", help="incrementally download changed notebooks")
    _add_source(pull_p)

    render_p = sub.add_parser("render", help="render changed bundles to PDF")
    _add_source(render_p)
    _add_output(render_p)
    _add_force(render_p)
    _add_include_trash(render_p)

    sync_p = sub.add_parser("sync", help="pull then render")
    _add_source(sync_p)
    _add_output(sync_p)
    _add_force(sync_p)
    _add_include_trash(sync_p)

    return parser


def _add_source(p: argparse.ArgumentParser) -> None:
    p.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="local notebook directory")


def _add_output(p: argparse.ArgumentParser) -> None:
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="PDF output directory")


def _add_force(p: argparse.ArgumentParser) -> None:
    p.add_argument("--force", action="store_true", help="re-render all bundles")


def _add_include_trash(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--include-trash",
        action="store_true",
        help="also render bundles under the source trash/ folder (off by default)",
    )


def _print_report(report: RenderReport) -> None:
    for path in report.rendered:
        print(f"rendered {path}")
    for warning in report.warnings:
        print(f"WARNING {warning}")
    for bundle_path, error in report.failed:
        print(f"FAILED {bundle_path}: {error}")
    print(
        f"{len(report.rendered)} rendered, "
        f"{len(report.skipped)} unchanged, "
        f"{len(report.trashed)} trashed-skipped, "
        f"{len(report.failed)} failed"
    )


if __name__ == "__main__":
    raise SystemExit(main())
