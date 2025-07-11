# AI News Agent - Current State

## Last Updated: 2025-07-11

## Recent Updates
- Fixed failing test in digest module (test_group_by_category)
- Conducted comprehensive code review
- Test coverage: 71.16% (target: 90%)

## Project Status
The AI News Agent is in active development. Core RSS collection and storage functionality has been implemented and tested.

## Completed Features

### RSS News Collector Module (✅ Completed)
- **Base Architecture**
  - Abstract `BaseCollector` class defining collector interface
  - Modular parser system with base parser and specialized implementations
  - Pydantic models for data validation (NewsItem, CollectorStats, etc.)
  - Configuration management with Pydantic Settings

- **RSS Collector Implementation**
  - Concurrent fetching from multiple RSS feeds using aiohttp
  - Exponential backoff retry logic for failed requests
  - Performance statistics tracking per feed
  - Automatic deduplication within collection batch
  - Age-based filtering (configurable max_age_days)
  - Feed-specific parsers:
    - StandardParser for regular RSS/Atom feeds
    - ArxivParser for ArXiv's Dublin Core format

- **Testing Infrastructure**
  - Comprehensive test suite with 82% coverage
  - Dynamic date generation in fixtures (future-proof tests)
  - Unit tests for parsers and validators
  - Integration tests with mocked HTTP responses
  - Error handling and edge case coverage

- **Modern Python Practices**
  - Python 3.11+ with type hints throughout
  - Async/await pattern for concurrent operations
  - Pydantic v2 for data validation
  - `uv` package manager integration
  - `ruff` for linting and formatting
  - Test-Driven Development (TDD) approach

### Storage Module (✅ Completed)
- **Database Architecture**
  - SQLAlchemy with async support (aiosqlite)
  - Alembic for database migrations
  - Repository pattern for clean data access
  - Timezone-aware datetime handling

- **Database Models**
  - NewsItemDB: Store collected news items
  - CollectorRunDB: Track collection runs and statistics
  - DailyDigestDB/WeeklySummaryDB: Store generated digests
  - DeduplicationCacheDB: Hash-based duplicate detection
  - DigestEntryDB: Link items to digests

- **Repository Implementations**
  - NewsItemRepository: CRUD operations for news items
  - CollectorRepository: Track collector runs and statistics
  - DigestRepository: Manage daily/weekly digests
  - DeduplicationRepository: Handle duplicate detection

- **Integration Features**
  - RSSCollectorWithStorage: Enhanced collector with DB persistence
  - Automatic deduplication on insert
  - Collection run tracking with statistics
  - Recent items query support

### Security Enhancements (✅ Completed)
- **Secret Detection**
  - Gitleaks configuration for pre-commit hooks
  - Custom secret scanner for configuration files
  - AI API key detection patterns

- **Prompt Injection Protection**
  - Comprehensive protection strategy documented
  - Input sanitization patterns
  - Content isolation mechanisms
  - Output validation

- **Code Security**
  - Rate limiting implementation
  - Input validation utilities
  - Safe logging practices

### Enhanced Deduplication Module (✅ Completed)
- **Embedding-based Similarity**
  - Sentence-transformers integration (all-MiniLM-L6-v2 model)
  - Semantic similarity detection for similar content
  - Configurable similarity threshold (default: 0.85)
  - Embedding caching for performance
  
- **Multi-Strategy Deduplication**
  - Exact URL matching (fastest)
  - Exact title/content hash matching
  - Semantic similarity with embeddings
  - Time-based filtering (avoid old false positives)
  
- **Performance Optimizations**
  - In-memory cache for recent items
  - Disk-based embedding cache
  - Batch processing for efficiency
  - Automatic cache cleanup
  
- **Integration Features**
  - Enhanced RSSCollectorWithStorage with semantic deduplication
  - DuplicateMatch result with similarity scores
  - Batch duplicate checking for multiple items

### Digest Generation Module (✅ Completed)
- **News Ranking System**
  - Multi-factor scoring (recency, relevance, diversity, content length)
  - Configurable weights for different signals
  - Source diversity enforcement
  - Category grouping and topic extraction
  
- **Multiple Output Formats**
  - Markdown formatter for plain text/email
  - HTML formatter with responsive design
  - Customizable templates and styling
  
- **Digest Types**
  - Daily digests with categorized news
  - Weekly summaries with top topics
  - AI summary integration (placeholder)
  
- **Storage Integration**
  - Automatic storage of generated digests
  - Tracking of sent/unsent digests
  - Regeneration support

## In Progress Features

### Scheduler Module
- Cron-based scheduling
- Daily digest at 20:00 Moscow time (Mon-Fri)
- Weekly summary at 11:00 Moscow time (Saturday)

## Technical Decisions

1. **Package Management**: Using `uv` instead of pip for faster dependency resolution
2. **Async Architecture**: Built on asyncio for efficient concurrent operations
3. **Testing Strategy**: Dynamic test data generation to avoid time-based failures
4. **Error Handling**: Graceful degradation with retry logic and statistics tracking
5. **Data Validation**: Pydantic models ensure data integrity throughout the pipeline

## Project Structure
```
ai-news-agent/
├── src/
│   └── ai_news_agent/
│       ├── __init__.py
│       ├── config.py          # Settings management
│       ├── models.py          # Pydantic data models
│       ├── collectors/
│       │   ├── __init__.py
│       │   ├── base.py        # Abstract base collector
│       │   ├── rss.py         # RSS collector implementation
│       │   ├── rss_with_storage.py # RSS with DB persistence
│       │   └── parsers/
│       │       ├── __init__.py
│       │       ├── base.py    # Base parser class
│       │       ├── standard.py # Standard RSS/Atom parser
│       │       └── arxiv.py   # ArXiv-specific parser
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── database.py    # Database connection management
│       │   ├── models.py      # SQLAlchemy models
│       │   └── repositories.py # Repository implementations
│       └── deduplication/
│           ├── __init__.py
│           ├── embeddings.py  # Embedding service
│           └── service.py     # Deduplication service
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest configuration
│   ├── test_rss_collector_simple.py
│   ├── test_rss_collector.py
│   ├── test_integration.py
│   ├── test_storage.py       # Storage module tests
│   ├── test_deduplication.py # Deduplication tests
│   └── fixtures/
│       └── rss_samples.py    # Dynamic test data
├── alembic/
│   ├── alembic.ini
│   └── env.py               # Alembic configuration
├── pyproject.toml           # Project configuration
└── .gitignore
```

## Dependencies
- Core: aiohttp, pydantic, pydantic-settings, feedparser, loguru, sqlalchemy, aiosqlite, alembic
- Deduplication: sentence-transformers, numpy
- Security: gitleaks, pre-commit, bleach
- Development: pytest, pytest-asyncio, pytest-cov, ruff, mypy

## Next Steps
1. Create scheduler module for automated collection
2. Add notification system integration
3. Implement CLI entry points
4. Create MCP server integration
5. Add AI service integration for enhanced summaries

## Known Issues
- None currently

## Notes for Future Development
- All tests use dynamic date generation to avoid future failures
- RSS collector supports concurrent fetching with configurable retry logic
- ArXiv feeds require special parsing due to Dublin Core metadata format
- Performance statistics are tracked per feed for monitoring