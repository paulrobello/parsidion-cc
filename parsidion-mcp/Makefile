.PHONY: install lint fmt typecheck test checkall build

build:
	@echo "No build step needed — editable install only."

install:
	uv tool install --editable .

fmt:
	uv run ruff format .

lint:
	uv run ruff check --fix .

typecheck:
	uv run pyright .

test:
	uv run pytest

checkall: fmt lint typecheck test
