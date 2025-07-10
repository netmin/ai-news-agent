# AI News Agent

AI-powered news aggregator with intelligent deduplication and multi-channel distribution.

## Features

- 📡 Collects AI/ML news from multiple RSS feeds
- 🔍 Intelligent deduplication (URL & title matching)
- 💾 SQLite storage with full history
- 📝 Beautiful markdown digests
- 🔌 MCP server for AI assistant integration
- ⏰ Automated schedule (weekdays 20:00 MSK, weekly summary Saturdays 11:00 MSK)

## Quick Start

### Prerequisites

Install [uv](https://github.com/astral-sh/uv) - the fast Python package manager:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup

1. Clone and setup:
```bash
cd /Users/vi/project/ai-news-agent
uv sync
```

2. Configure:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Run:
```bash
# Run manual collection
uv run ai-news collect

# Generate daily digest
uv run ai-news digest

# Generate weekly summary
uv run ai-news weekly

# Start MCP server
uv run ai-news serve
```

### Development

```bash
# Run tests
uv run pytest

# Format code
uv run black .
uv run ruff . --fix

# Type check
uv run mypy .
```

## Architecture

Built with modern Python practices:
- **Python 3.11+** with latest features
- **Pydantic** for data validation
- **AsyncIO** for concurrent operations
- **Type hints** everywhere
- **Structured logging** with loguru

See `context/ARCHITECTURE.md` for detailed design decisions.

## Schedule

- **Daily Digest**: Monday-Friday at 20:00 MSK
- **Weekly Summary**: Saturday at 11:00 MSK
- **Sunday**: Rest day (no operations)

## Project Structure

```
ai-news-agent/
├── src/ai_news_agent/   # Main package
├── tests/               # Test suite
├── context/             # Project documentation
├── data/               # Local storage
└── output/             # Generated digests
```

## License

MIT