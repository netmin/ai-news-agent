"""Simple tests for RSS collector to verify basic functionality"""

from datetime import UTC, datetime

import pytest

from ai_news_agent.collectors.parsers.arxiv import ArxivParser
from ai_news_agent.collectors.parsers.standard import StandardParser
from ai_news_agent.collectors.rss import RSSCollector
from ai_news_agent.models import NewsItem

from .fixtures.rss_samples import ARXIV_RSS, EMPTY_RSS, TECHCRUNCH_RSS


@pytest.mark.asyncio
async def test_standard_parser():
    """Test standard RSS parser directly"""
    parser = StandardParser("Test Feed")
    items = await parser.parse(TECHCRUNCH_RSS)

    assert len(items) == 2
    assert (
        items[0].title == "OpenAI launches new GPT-5 model with enhanced capabilities"
    )
    assert str(items[0].url) == "https://techcrunch.com/2024/01/15/openai-gpt5-launch/"
    assert items[0].source == "Test Feed"
    assert "OpenAI has announced" in items[0].content


@pytest.mark.asyncio
async def test_arxiv_parser():
    """Test ArXiv RSS parser directly"""
    parser = ArxivParser("ArXiv Test")
    items = await parser.parse(ARXIV_RSS)

    assert len(items) == 2
    assert (
        items[0].title == "Efficient Transformer Architecture for Large Language Models"
    )
    assert str(items[0].url) == "http://arxiv.org/abs/2401.12345"
    assert items[0].source == "ArXiv Test"
    assert "John Doe" in items[0].metadata.get("authors", "")


@pytest.mark.asyncio
async def test_empty_feed_parsing():
    """Test parsing empty RSS feed"""
    parser = StandardParser("Empty Feed")
    items = await parser.parse(EMPTY_RSS)

    assert len(items) == 0


@pytest.mark.asyncio
async def test_news_item_id_generation():
    """Test NewsItem ID auto-generation"""
    item = NewsItem(
        url="https://example.com/article",
        title="Test Article",
        source="Test Source",
        published_at=datetime.now(UTC),
    )

    # ID should be generated from URL + title
    assert item.id is not None
    assert len(item.id) == 64  # SHA256 hex length


@pytest.mark.asyncio
async def test_collector_initialization():
    """Test RSS collector initialization"""
    collector = RSSCollector()

    # Should initialize stats for all configured feeds
    stats = await collector.get_stats()
    assert len(stats) >= 5  # At least 5 feeds configured

    # All stats should start at zero
    for stat in stats:
        assert stat.success_count == 0
        assert stat.failure_count == 0
        assert stat.success_rate == 0.0
