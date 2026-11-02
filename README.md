# rmsync

Sync reMarkable notebooks from the cloud and render them to readable,
rasterizable PDFs — one PDF per notebook, mirroring your reMarkable folders.

## How it works

- `rmsync pull` incrementally downloads changed notebooks via `rmapi`.
- `rmsync render` turns changed `.rmdoc` bundles into one PDF per notebook.
- `rmsync sync` runs `pull` then `render`.

Handwritten notebooks are rendered with a pure-Python chain
(`rmc` → SVG → `cairosvg` → PDF, merged with `pypdf`); no Inkscape or poppler
required. Imported documents emit their embedded PDF directly. See
[`design_decisions/`](design_decisions/) for why.

## Requirements

`rmsync` shells out to [`rmapi`](https://github.com/ddvk/rmapi) for cloud
access. Install and authenticate it separately; `rmsync` looks for it on `PATH`
or at `~/go/bin/rmapi` and errors clearly if it is missing. Its auth lives
outside this tool.

## Install

From the project directory, put `rmsync` on your `PATH`:

```sh
uv tool install .
rmsync --help
```

## Usage

```sh
rmsync pull                      # download changed notebooks
rmsync render                    # render changed notebooks to PDF
rmsync render --force            # re-render everything
rmsync sync                      # pull then render

# custom locations (defaults shown)
rmsync sync --source ~/remarkable --output ~/remarkable-pdf
```

Defaults: source `~/remarkable`, output `~/remarkable-pdf`.
Renders are incremental — a notebook is skipped when its PDF is newer than the
source bundle; `--force` overrides that.

## Development

```sh
just install   # sync dev environment
just test      # run pytest
just lint      # ruff check + format --check
```
