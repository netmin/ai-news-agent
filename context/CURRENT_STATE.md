# Current Project State

Last Updated: 2025-01-15

## Completed
- ✅ Linear project created with tasks
- ✅ Project structure initialized with modern Python setup
- ✅ Using `uv` for dependency management
- ✅ Pydantic models defined
- ✅ Configuration system with Pydantic Settings
- ✅ Schedule configured for MSK timezone (Mon-Fri 20:00, Sat 11:00)

## In Progress
- 🔄 Setting up development environment
- 🔄 Creating base interfaces for collectors

## Next Steps
1. Implement RSS collector with TDD approach
2. Set up SQLite database with aiosqlite
3. Create simple deduplicator
4. Build scheduler with croniter
5. Test with real feeds

## Recent Decisions
- Using `uv` instead of pip for modern Python workflow
- Pydantic for all data validation
- AsyncIO by default for all I/O operations
- Moscow timezone for scheduling
- Python 3.11+ for latest features

## Tech Stack Finalized
- Python 3.11+
- uv (package manager)
- Pydantic 2.x
- aiohttp & aiosqlite
- loguru for logging
- croniter for scheduling

## Commands to Run
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup project
cd /Users/vi/project/ai-news-agent
uv sync

# Copy env file
cp .env.example .env
```

## Notes for Next Session
- Start with tests/test_rss_collector.py
- Use feedparser library for RSS parsing
- Mock aiohttp responses in tests
- Focus on TechCrunch feed first for testing
