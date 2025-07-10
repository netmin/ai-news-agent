# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered news aggregator focused on AI/ML content. Built with Python 3.11+, async-first architecture, and Pydantic validation. Currently in MVP development stage.

## Development Commands

```bash
# Environment setup
make setup          # Install uv and dependencies
make dev           # Start development container
make shell         # Access development container shell

# Development workflow
make test          # Run tests in Docker
make test-local    # Run tests locally (requires uv)
make format        # Format code with black
make lint          # Run ruff and mypy checks

# Running services
make run-collect   # Collect news from RSS feeds
make run-digest    # Generate daily digest
make run-weekly    # Generate weekly summary
```

## Architecture

The codebase follows a modular async architecture:

1. **Entry Points**: 
   - `src/ai_news_agent/cli.py` - CLI commands (to be implemented)
   - Future: MCP server for AI assistant integration

2. **Core Components**:
   - `models.py` - Pydantic models define all data structures with validation
   - `config.py` - Centralized configuration using Pydantic Settings
   - `collectors/` - RSS feed collectors with feed-specific parsing
   - `storage/` - SQLite persistence layer (to be implemented)
   - `processors/` - Deduplication and summarization logic (to be implemented)

3. **Data Flow**:
   ```
   RSS Feeds → Collectors → Storage → Processors → Output (Markdown)
   ```

4. **Async Patterns**:
   - All I/O operations use asyncio
   - aiosqlite for database operations
   - httpx for HTTP requests
   - Concurrent feed collection

## Critical Development Rules

1. **Package Management**: Use `uv` not pip. Example:
   ```bash
   uv add package-name
   uv sync
   ```

2. **Testing**: TDD is mandatory. Write failing tests first:
   ```bash
   # Run specific test
   uv run pytest tests/test_module.py::test_function -v
   
   # Run with coverage
   uv run pytest --cov=ai_news_agent --cov-report=term-missing
   ```

3. **Type Safety**: All functions must have type hints. Mypy strict mode.

4. **Async First**: No synchronous I/O. Use async/await for all I/O operations.

5. **Validation**: Use Pydantic models, never raw dicts for data structures.

## Key Implementation Details

### RSS Feed Handling
- ArXiv uses `<dc:creator>` instead of `<author>` tag
- Some feeds provide full content, others summaries
- Implement retry logic with exponential backoff
- Each feed may need custom parsing logic

### Database Schema
- SQLite for local development, PostgreSQL-ready
- Use aiosqlite for async operations
- Migrations handled manually for now

### Scheduling
- Daily digest: Mon-Fri 20:00 MSK
- Weekly summary: Sat 11:00 MSK
- Sunday: No operations
- All internal times in UTC, display in Moscow timezone

### Testing Strategy
```python
# Example test structure
@pytest.mark.asyncio
async def test_collector():
    # Use fixtures for mock RSS data
    # Mock httpx responses
    # Assert Pydantic model validation
```

## Project Context

See `/context/` directory for detailed project documentation:
- `PROJECT_CONTEXT.md` - Full project specification
- `CURRENT_STATE.md` - Implementation status tracker