# Hierarchical Agents Makefile

.PHONY: help install install-dev test test-cov lint format type-check clean build docs serve

# Default target
help:
	@echo "Available commands:"
	@echo "  install      Install package in production mode"
	@echo "  install-dev  Install package in development mode with dev dependencies"
	@echo "  test         Run tests"
	@echo "  test-cov     Run tests with coverage report"
	@echo "  lint         Run linting (flake8)"
	@echo "  format       Format code (black + isort)"
	@echo "  type-check   Run type checking (mypy)"
	@echo "  clean        Clean build artifacts"
	@echo "  build        Build package"
	@echo "  docs         Build documentation"
	@echo "  serve        Start development server"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

# Testing
test:
	pytest

test-cov:
	pytest --cov=src/hierarchical_agents --cov-report=html --cov-report=term

# Code quality
lint:
	flake8 src/ tests/

format:
	black src/ tests/
	isort src/ tests/

type-check:
	mypy src/

# Quality check all
check: format lint type-check test

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

# Build
build: clean
	python -m build

# Documentation
docs:
	mkdocs build

docs-serve:
	mkdocs serve

# Development server
serve:
	uvicorn hierarchical_agents.main:app --reload --host 0.0.0.0 --port 8000

# Docker
docker-build:
	docker build -t hierarchical-agents .

docker-run:
	docker run -p 8000:8000 --env-file .env hierarchical-agents