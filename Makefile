.PHONY: fix lint test

fix:
	uv run ruff check --fix .
	uv run ruff format .

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest

