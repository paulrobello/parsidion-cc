.PHONY: build test lint fmt typecheck checkall clean install

# Format code with ruff
fmt:
	uv run ruff format .

# Lint code with ruff
lint:
	uv run ruff check .

# Type check with pyright
typecheck:
	uv run pyright .

# Run tests
test:
	uv run pytest tests/

# Run all checks in sequence: format, lint, typecheck, test
checkall: fmt lint typecheck test

# Build (no-op for this project — it is managed configuration, not a compiled artifact)
build:
	@echo "parsidion-cc is a configuration toolkit — no build step required."

# Clean generated artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

# Install skill to ~/.claude (shortcut for uv run install.py --force --yes)
install:
	uv run install.py --force --yes
