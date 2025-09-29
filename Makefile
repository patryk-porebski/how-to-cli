.PHONY: run build publish install install-dev test clean lint format help

# Default target
help:
	@echo "Available targets:"
	@echo "  run          - Run the how CLI application"
	@echo "  build        - Build the package for distribution"
	@echo "  publish      - Publish package to PyPI"
	@echo "  install      - Install the package in development mode"
	@echo "  install-dev  - Install with development dependencies"
	@echo "  test         - Run the test suite"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code with black and isort"
	@echo "  clean        - Clean build artifacts"

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
