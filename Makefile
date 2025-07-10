.PHONY: help setup dev test run clean docker-build docker-up docker-down

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Initial project setup
	curl -LsSf https://astral.sh/uv/install.sh | sh || true
	uv sync
	cp -n .env.example .env || true
	@echo "✅ Setup complete! Edit .env file if needed"

dev: ## Start development environment in Docker
	docker-compose --profile dev up -d
	@echo "✅ Dev container started! Use 'make shell' to access"

shell: ## Access development container shell
	docker exec -it ai-news-dev bash

test: ## Run tests in Docker
	docker-compose --profile test up --abort-on-container-exit

test-local: ## Run tests locally
	uv run pytest -v

run-collect: ## Run news collection
	uv run python -m ai_news_agent.cli collect

run-digest: ## Generate daily digest
	uv run python -m ai_news_agent.cli digest

run-weekly: ## Generate weekly summary
	uv run python -m ai_news_agent.cli weekly

format: ## Format code with black and ruff
	uv run black src/ tests/
	uv run ruff --fix src/ tests/

lint: ## Run linting checks
	uv run black --check src/ tests/
	uv run ruff src/ tests/
	uv run mypy src/

docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start all services in Docker
	docker-compose up -d

docker-down: ## Stop all Docker services
	docker-compose down

docker-logs: ## Show Docker logs
	docker-compose logs -f

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage
	@echo "✅ Cleaned up!"

# Development shortcuts
d: dev
s: shell
t: test
f: format
l: lint
