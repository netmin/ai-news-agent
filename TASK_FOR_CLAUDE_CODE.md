# 🎯 Task: Build RSS News Collector Module with Modern Python

**Linear Issue:** [ITV-134](https://linear.app/itvibe/issue/ITV-134)

## Context
You're building the first component of an AI News Agent system. This project uses modern Python practices:
- Python 3.11+ with latest features
- `uv` for package management (not pip!)
- Pydantic for data validation
- Docker for consistent development
- Type hints everywhere
- AsyncIO by default

Read these files first:
1. `context/PROJECT_CONTEXT.md` - Full project overview
2. `src/ai_news_agent/models.py` - Pydantic models already defined
3. `src/ai_news_agent/config.py` - Settings management

## Objective
Create a robust RSS collector that:
- Fetches news from multiple RSS feeds concurrently
- Validates data using existing Pydantic models
- Handles errors gracefully with retries
- Provides detailed logging
- Works in Docker environment

## Technical Requirements

### Must Use:
- **Existing Models**: Use `NewsItem` from `models.py` (don't redefine!)
- **Settings**: Use `settings` from `config.py` for configuration
- **AsyncIO**: All I/O operations must be async
- **Type Hints**: Every function parameter and return type
- **Pydantic**: For all data validation
- **Loguru**: For logging (not standard logging)

### Architecture:
```python
# src/ai_news_agent/collectors/base.py
from abc import ABC, abstractmethod
from typing import List
from ..models import NewsItem, CollectorStats

class BaseCollector(ABC):
    @abstractmethod
    async def collect(self) -> List[NewsItem]:
        """Collect news items from source"""
        pass
    
    @abstractmethod
    async def get_stats(self) -> CollectorStats:
        """Get collector performance statistics"""
        pass
```

### RSS Feeds to Support:
Already configured in `config.py`:
- TechCrunch AI
- The Verge AI  
- ArXiv AI Papers
- OpenAI Blog
- Anthropic Blog

## Implementation Plan

### 1. Test-Driven Development
Create `tests/test_rss_collector.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from ai_news_agent.models import NewsItem
from ai_news_agent.collectors.rss import RSSCollector

@pytest.mark.asyncio
async def test_collector_parses_valid_feed():
    """Should parse RSS feed and return NewsItem objects"""
    # Mock RSS XML response
    # Assert NewsItem validation
    # Check all required fields

@pytest.mark.asyncio
async def test_collector_filters_old_articles():
    """Should skip articles older than max_age_days"""
    # Include old and new articles
    # Assert only recent ones returned

@pytest.mark.asyncio
async def test_collector_handles_network_errors():
    """Should retry on failure with exponential backoff"""
    # Mock timeout, 404, 500 errors
    # Assert retry behavior

@pytest.mark.asyncio
async def test_collector_deduplicates_within_batch():
    """Should not return duplicate items from same collection"""
    # Mock feed with duplicate entries
    # Assert unique items only

@pytest.mark.asyncio  
async def test_arxiv_special_handling():
    """Should handle ArXiv's unique RSS structure"""
    # ArXiv uses different field names
    # Assert correct field mapping
```

### 2. Implementation Structure

```
src/ai_news_agent/collectors/
├── __init__.py
├── base.py          # Abstract base class
├── rss.py           # Main RSS collector
└── parsers/         # Feed-specific parsers
    ├── __init__.py
    ├── base.py      # Base parser
    ├── standard.py  # Standard RSS/Atom
    └── arxiv.py     # ArXiv special handling
```

### 3. Key Features to Implement

1. **Concurrent fetching** with `aiohttp.ClientSession`
2. **Retry logic** with exponential backoff
3. **Feed-specific parsers** (ArXiv has different structure)
4. **Progress tracking** with loguru
5. **Statistics collection** for monitoring
6. **Graceful degradation** if some feeds fail

## Docker Development Workflow

```bash
# Start development container
docker-compose --profile dev up -d

# Run tests in container
docker-compose --profile test up

# Access dev container
docker exec -it ai-news-dev bash

# Inside container:
uv run pytest tests/test_rss_collector.py -v
uv run python -m ai_news_agent.collectors.rss  # Test module directly
```

## Deliverables

1. **Base Implementation**:
   - `src/ai_news_agent/collectors/__init__.py`
   - `src/ai_news_agent/collectors/base.py`
   - `src/ai_news_agent/collectors/rss.py`

2. **Feed Parsers**:
   - `src/ai_news_agent/collectors/parsers/base.py`
   - `src/ai_news_agent/collectors/parsers/standard.py`
   - `src/ai_news_agent/collectors/parsers/arxiv.py`

3. **Tests**:
   - `tests/test_rss_collector.py`
   - `tests/fixtures/rss_samples.py` (mock data)

4. **Documentation**:
   - Update `context/CURRENT_STATE.md`
   - Add docstrings with usage examples

## Success Criteria

- [ ] All tests pass (`uv run pytest`)
- [ ] Type checking passes (`uv run mypy src/`)
- [ ] Can collect from all 5 configured feeds
- [ ] Handles failures gracefully (doesn't crash on one bad feed)
- [ ] Logs are informative and structured
- [ ] Works in Docker environment
- [ ] Statistics tracking implemented

## Example Usage

```python
from ai_news_agent.collectors.rss import RSSCollector
from ai_news_agent.config import settings

# Collector uses settings automatically
collector = RSSCollector()

# Collect from all configured feeds
items = await collector.collect()
print(f"Collected {len(items)} news items")

# Get performance stats
stats = await collector.get_stats()
for stat in stats:
    print(f"{stat.source}: {stat.success_rate:.1%} success rate")
```

## Important Notes

1. **Don't redefine models** - use existing Pydantic models
2. **Use settings object** - don't hardcode configuration  
3. **Moscow timezone** - all scheduling in MSK (configured in Docker)
4. **Async everything** - no synchronous I/O operations
5. **Log don't print** - use loguru for all output

## Hints for Implementation

- Start by examining actual RSS feed responses
- ArXiv uses `<dc:creator>` instead of `<author>`
- Some feeds have full content, others just summaries
- Use `aiohttp.ClientTimeout` for timeout management
- Consider feed health metrics for monitoring
- Remember to handle XML parsing errors gracefully

Remember: Modern Python, type safety, and production-ready code!
