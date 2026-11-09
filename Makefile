.PHONY: install test lint

# First run creates uv.lock; later runs install exactly what it records.
install:
	if [ -f uv.lock ]; then uv sync --locked; else uv sync; fi

test:
	uv run pytest -q

lint:
	uv run ruff check .
