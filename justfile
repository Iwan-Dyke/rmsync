# rmsync developer tasks

# sync the dev environment
install:
    uv sync

# run the test suite
test:
    uv run pytest

# lint and check formatting
lint:
    uv run ruff check .
    uv run ruff format --check .

# auto-format
format:
    uv run ruff format .

# install the rmsync command on PATH
install-tool:
    uv tool install .
