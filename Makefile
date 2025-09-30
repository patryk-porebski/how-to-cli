.PHONY: run build publish install install-dev test clean lint format help brew-release brew-sha256 brew-test brew-update-tap

# Default target
help:
	@echo "Available targets:"
	@echo "  run              - Run the how CLI application"
	@echo "  build            - Build the package for distribution"
	@echo "  publish          - Publish package to PyPI"
	@echo "  install          - Install the package in development mode"
	@echo "  install-dev      - Install with development dependencies"
	@echo "  test             - Run the test suite"
	@echo "  lint             - Run linting checks"
	@echo "  format           - Format code with black and isort"
	@echo "  clean            - Clean build artifacts"
	@echo ""
	@echo "Homebrew release targets:"
	@echo "  brew-release     - Create and push git tag for Homebrew release"
	@echo "  brew-sha256      - Get SHA256 hash for current version"
	@echo "  brew-update-tap  - Update local Homebrew tap with current formula"
	@echo "  brew-test        - Test Homebrew installation"

# Run the application
run:
	python how.py

# Build the package
build:
	python -m pip install --upgrade build
	python -m build

# Publish to PyPI
publish: build
	python -m pip install --upgrade twine
	python -m twine upload dist/*

# Install in development mode
install:
	pip install -e .

# Install with development dependencies
install-dev:
	pip install -e ".[dev]"

# Run tests
test:
	python -m pytest tests/ -v

# Run linting
lint:
	python -m flake8 .
	python -m mypy .

# Format code
format:
	python -m black .
	python -m isort .

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Homebrew release targets
VERSION := $(shell grep '^version' pyproject.toml | cut -d'"' -f2)

brew-release:
	@echo "Creating and pushing release v$(VERSION)..."
	@git add pyproject.toml constants.py how-to-cli.rb MANIFEST.in
	@git commit -m "Release v$(VERSION)" || true
	@git push origin main
	@git tag -a v$(VERSION) -m "Release v$(VERSION)"
	@git push origin v$(VERSION)
	@echo "✓ Tag v$(VERSION) created and pushed"
	@echo ""
	@echo "Next steps:"
	@echo "1. Create GitHub release at: https://github.com/patryk-porebski/how-to-cli/releases/new"
	@echo "2. Run 'make brew-sha256' to get the SHA256 hash"
	@echo "3. Update how-to-cli.rb with the SHA256"
	@echo "4. Run 'make brew-update-tap' to update your tap"
	@echo "5. Run 'make brew-test' to test installation"

brew-sha256:
	@echo "Getting SHA256 for v$(VERSION)..."
	@curl -sL https://github.com/patryk-porebski/how-to-cli/archive/refs/tags/v$(VERSION).tar.gz | shasum -a 256
	@echo ""
	@echo "Update this hash in how-to-cli.rb"

brew-update-tap:
	@echo "Copying formula to Homebrew tap..."
	@cp how-to-cli.rb $$(brew --repository)/Library/Taps/patryk-porebski/homebrew-tap/Formula/how-to-cli.rb
	@echo "✓ Formula updated in tap"
	@echo ""
	@echo "To publish to GitHub, run:"
	@echo "  cd $$(brew --repository)/Library/Taps/patryk-porebski/homebrew-tap"
	@echo "  git add Formula/how-to-cli.rb"
	@echo "  git commit -m 'Update how-to-cli to v$(VERSION)'"
	@echo "  git push"

brew-test:
	@echo "Testing Homebrew installation..."
	@brew uninstall how-to-cli 2>/dev/null || true
	@brew install patryk-porebski/tap/how-to-cli
	@echo ""
	@echo "Testing installed binary..."
	@how version
	@echo ""
	@echo "✓ Installation successful!"
