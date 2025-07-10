# AI News Agent - Project Context

## Overview
AI-powered news aggregator focused on AI/ML content with intelligent deduplication and multi-channel distribution. Built with Claude Code development in mind.

## Project Links
- Linear Project: https://linear.app/itvibe/project/ai-news-agent-500b7f14722e
- GitHub: [To be created]

## Current Status
- Phase: Initial Setup
- Sprint: MVP Development
- Last Updated: 2025-01-15

## Architecture Principles
1. **Modularity** - Each component in separate file for easy Claude Code navigation
2. **Clear Interfaces** - Well-defined contracts between modules
3. **Progressive Enhancement** - Start simple, easy to extend
4. **AI-Friendly** - Self-documenting code with examples
5. **Type Safety** - Using Pydantic for runtime validation

## Tech Stack
- **Python 3.11+** - Modern Python with all latest features
- **uv** - Fast Python package manager
- **Pydantic** - Data validation and settings management
- **AsyncIO** - Concurrent operations
- **SQLite** - Local storage (upgradeable to PostgreSQL)
- **Loguru** - Structured logging

## Schedule
- **Daily Digest**: Monday-Friday at 20:00 MSK (17:00 UTC)
- **Weekly Summary**: Saturday at 11:00 MSK (08:00 UTC)
- **Sunday**: No operations (rest day)

## Project Structure
```
ai-news-agent/
├── context/              # Project context for AI
│   ├── PROJECT_CONTEXT.md
│   ├── ARCHITECTURE.md
│   ├── CURRENT_STATE.md
│   └── API_CONTRACTS.md
├── src/
│   └── ai_news_agent/   # Main package
│       ├── __init__.py
│       ├── cli.py       # CLI entry point
│       ├── config.py    # Pydantic settings
│       ├── models.py    # Pydantic models
│       ├── collectors/  # Source collectors
│       ├── processors/  # Data processing
│       ├── storage/     # Data persistence
│       ├── outputs/     # Output adapters
│       └── orchestrator.py
├── tests/              # Test files
├── data/              # Local data storage
├── output/            # Generated outputs
├── pyproject.toml     # Modern Python project config
├── .env              # Environment variables
└── README.md
```

## MVP Features (Current Sprint)
1. ✅ Project setup with uv and modern Python
2. ⏳ RSS collector for 5-6 AI news sources
3. ⏳ Simple URL & title-based deduplication
4. ⏳ SQLite storage with Pydantic models
5. ⏳ Markdown output formatter
6. ⏳ Cron-based scheduler
7. ⏳ MCP server integration

## Data Flow
```
RSS Feeds → Collector → Deduplicator → Storage → Formatter → Output
                            ↓
                     SQLite Database
```

## Key Models (Pydantic)

```python
from pydantic import BaseModel, HttpUrl
from datetime import datetime

class NewsItem(BaseModel):
    id: str  # SHA256 hash
    url: HttpUrl
    title: str
    content: str
    summary: str
    source: str
    published_at: datetime
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = []
    metadata: dict = {}
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

## Configuration (Pydantic Settings)
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Schedule
    daily_schedule: str = "0 20 * * 1-5"  # Mon-Fri 20:00 MSK
    weekly_schedule: str = "0 11 * * 6"   # Sat 11:00 MSK
    timezone: str = "Europe/Moscow"
    
    # Storage
    database_url: str = "sqlite+aiosqlite:///./data/news.db"
    
    # Processing
    max_age_days: int = 7
    title_similarity_threshold: float = 0.85
    
    class Config:
        env_file = ".env"
        env_prefix = "AI_NEWS_"
```

## Development Workflow
1. Always use `uv` for dependency management
2. Run tests with `uv run pytest`
3. Format code with `uv run black .` and `uv run ruff .`
4. Type check with `uv run mypy .`
5. Update CURRENT_STATE.md after each session

## CLI Commands
```bash
# Install dependencies
uv sync

# Run collector
uv run ai-news collect

# Generate daily digest
uv run ai-news digest

# Generate weekly summary
uv run ai-news weekly

# Run MCP server
uv run ai-news serve
```

## Next Steps
1. Set up basic project structure
2. Implement RSS collector with Pydantic models
3. Create SQLite storage with aiosqlite
4. Build cron scheduler for MSK timezone

## Questions/Decisions Pending
- [ ] Which LLM API for summarization? (Anthropic/OpenAI/Local)
- [ ] Deploy strategy? (VPS/Cloud Function/Container)
- [ ] Monitoring and alerting approach?

## For Claude Code
When starting a session:
1. Read this file first
2. Check CURRENT_STATE.md for latest progress
3. Use `uv` for all Python operations
4. Follow type hints strictly
5. Update context files after changes

Remember: Modern Python patterns, async by default, type safety first!