"""Comprehensive tests for RSS collector module"""

from unittest.mock import patch

import aiohttp
import pytest

from ai_news_agent.collectors.rss import RSSCollector
from ai_news_agent.config import settings
from ai_news_agent.models import NewsItem

from .fixtures.rss_samples import (
    ARXIV_RSS,
    DUPLICATE_RSS,
    EMPTY_RSS,
    MALFORMED_RSS,
    OLD_ARTICLE_RSS,
    TECHCRUNCH_RSS,
    VERGE_RSS,
)


class MockResponse:
    """Mock aiohttp response"""

    def __init__(self, text: str, status: int = 200):
        self._text = text
        self.status = status
        self.request_info = None
        self.history = []

    async def text(self) -> str:
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_collector_parses_valid_techcrunch_feed():
    """Should parse TechCrunch RSS feed and return NewsItem objects"""

    # Use a single feed for focused testing
    test_feeds = [{"url": "https://techcrunch.com/feed", "name": "TechCrunch AI"}]

    async def mock_request(self, method, url, **kwargs):
        return MockResponse(TECHCRUNCH_RSS)

    with patch.object(settings, "rss_feeds", test_feeds):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            assert len(items) == 2
            assert all(isinstance(item, NewsItem) for item in items)

            # Check first item
            assert (
                items[0].title
                == "OpenAI launches new GPT-5 model with enhanced capabilities"
            )
            assert (
                str(items[0].url) == "https://techcrunch.com/2024/01/15/openai-gpt5-launch/"
            )
            assert items[0].source == "TechCrunch AI"
            assert "OpenAI has announced" in items[0].content


@pytest.mark.asyncio
async def test_collector_parses_arxiv_special_format():
    """Should handle ArXiv's unique RSS structure with dc:creator tags"""

    # Mock only the ArXiv feed
    feeds_config = [{"url": "https://arxiv.org/rss/cs.AI", "name": "ArXiv AI Papers"}]

    async def mock_request(self, method, url, **kwargs):
        return MockResponse(ARXIV_RSS)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            assert len(items) == 2
            assert (
                items[0].title
                == "Efficient Transformer Architecture for Large Language Models"
            )
            assert str(items[0].url) == "http://arxiv.org/abs/2401.12345"
            assert items[0].source == "ArXiv AI Papers"
            # ArXiv uses dc:creator which should be in metadata
            assert "John Doe" in items[0].metadata.get("authors", "")


@pytest.mark.asyncio
async def test_collector_filters_old_articles():
    """Should skip articles older than max_age_days"""

    feeds_config = [{"url": "https://example.com/feed", "name": "Test Feed"}]

    async def mock_request(self, method, url, **kwargs):
        return MockResponse(OLD_ARTICLE_RSS)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            # Should only get the recent article, not the old one
            assert len(items) == 1
            assert items[0].title == "Recent AI Development"


@pytest.mark.asyncio
async def test_collector_handles_network_errors_with_retry():
    """Should retry on failure with exponential backoff"""

    feeds_config = [{"url": "https://example.com/feed", "name": "Test Feed"}]

    call_count = 0

    async def mock_request(self, method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise aiohttp.ClientError("Network error")
        return MockResponse(TECHCRUNCH_RSS)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            # Should eventually succeed and return items
            assert len(items) == 2
            assert call_count == 3  # Initial + 2 retries


@pytest.mark.asyncio
async def test_collector_handles_timeout():
    """Should handle timeout errors gracefully"""

    feeds_config = [
        {"url": "https://example.com/feed1", "name": "Feed 1"},
        {"url": "https://example.com/feed2", "name": "Feed 2"},
    ]

    async def mock_request(self, method, url, **kwargs):
        if "feed1" in url:
            raise TimeoutError()
        return MockResponse(TECHCRUNCH_RSS)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            # Should get items from successful feed only
            assert len(items) == 2
            assert all(item.source == "Feed 2" for item in items)


@pytest.mark.asyncio
async def test_collector_deduplicates_within_batch():
    """Should not return duplicate items from same collection"""

    feeds_config = [{"url": "https://example.com/feed", "name": "Test Feed"}]

    async def mock_request(self, method, url, **kwargs):
        return MockResponse(DUPLICATE_RSS)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            # Should deduplicate identical items
            assert len(items) == 2  # Not 3
            titles = [item.title for item in items]
            assert titles.count("Breaking: Major AI Breakthrough") == 1
            assert "Different Article" in titles


@pytest.mark.asyncio
async def test_collector_handles_malformed_rss():
    """Should handle malformed RSS gracefully without crashing"""

    feeds_config = [
        {"url": "https://example.com/malformed", "name": "Malformed Feed"},
        {"url": "https://example.com/good", "name": "Good Feed"},
    ]

    async def mock_request(self, method, url, **kwargs):
        if "malformed" in url:
            return MockResponse(MALFORMED_RSS)
        return MockResponse(TECHCRUNCH_RSS)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            # Should still get items from good feed
            assert len(items) > 0
            assert all(item.source == "Good Feed" for item in items)


@pytest.mark.asyncio
async def test_collector_handles_empty_feeds():
    """Should handle empty RSS feeds gracefully"""

    feeds_config = [{"url": "https://example.com/empty", "name": "Empty Feed"}]

    async def mock_request(self, method, url, **kwargs):
        return MockResponse(EMPTY_RSS)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            assert len(items) == 0


@pytest.mark.asyncio
async def test_collector_concurrent_fetching():
    """Should fetch from multiple feeds concurrently"""

    # Test with specific feeds
    test_feeds = [
        {"url": "https://techcrunch.com/feed", "name": "TechCrunch AI"},
        {"url": "https://verge.com/feed", "name": "The Verge AI"},
        {"url": "https://arxiv.org/feed", "name": "ArXiv AI Papers"},
    ]

    async def mock_request(self, method, url, **kwargs):
        if "techcrunch" in url:
            return MockResponse(TECHCRUNCH_RSS)
        elif "verge" in url:
            return MockResponse(VERGE_RSS)
        elif "arxiv" in url:
            return MockResponse(ARXIV_RSS)
        else:
            return MockResponse(EMPTY_RSS)

    with patch.object(settings, "rss_feeds", test_feeds):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            # Should get items from all feeds
            sources = {item.source for item in items}
            assert len(sources) == 3  # All 3 feeds
            assert len(items) >= 3  # At least one item per feed


@pytest.mark.asyncio
async def test_collector_statistics_tracking():
    """Should track performance statistics correctly"""

    feeds_config = [
        {"url": "https://example.com/feed1", "name": "Feed 1"},
        {"url": "https://example.com/feed2", "name": "Feed 2"},
    ]

    async def mock_request(self, method, url, **kwargs):
        if "feed1" in url:
            raise aiohttp.ClientError("Failed")
        return MockResponse(TECHCRUNCH_RSS)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            await collector.collect()
            stats = await collector.get_stats()

            assert len(stats) == 2

            # Check Feed 1 stats (failed)
            feed1_stats = next(s for s in stats if s.source == "Feed 1")
            assert feed1_stats.failure_count > 0
            assert feed1_stats.success_count == 0
            assert feed1_stats.success_rate == 0.0
            assert feed1_stats.health_status == "unhealthy"

            # Check Feed 2 stats (succeeded)
            feed2_stats = next(s for s in stats if s.source == "Feed 2")
            assert feed2_stats.success_count > 0
            assert feed2_stats.failure_count == 0
            assert feed2_stats.success_rate == 1.0
            assert feed2_stats.health_status == "healthy"


@pytest.mark.asyncio
async def test_collector_respects_timeout_setting():
    """Should respect timeout configuration"""

    feeds_config = [{"url": "https://example.com/feed", "name": "Test Feed"}]

    captured_kwargs = None

    async def mock_request(self, method, url, **kwargs):
        nonlocal captured_kwargs
        captured_kwargs = kwargs
        return MockResponse(TECHCRUNCH_RSS)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch.object(settings, "request_timeout", 5):  # 5 second timeout
            with patch("aiohttp.ClientSession._request", mock_request):
                collector = RSSCollector()
                await collector.collect()

                # Check that timeout was passed to aiohttp
                assert captured_kwargs is not None
                assert "timeout" in captured_kwargs
                assert captured_kwargs["timeout"].total == 5


@pytest.mark.asyncio
async def test_collector_handles_http_errors():
    """Should handle various HTTP error codes gracefully"""

    feeds_config = [
        {"url": "https://example.com/404", "name": "404 Feed"},
        {"url": "https://example.com/500", "name": "500 Feed"},
        {"url": "https://example.com/200", "name": "Good Feed"},
    ]

    async def mock_request(self, method, url, **kwargs):
        if "404" in url:
            resp = MockResponse("Not Found", status=404)
            raise aiohttp.ClientResponseError(
                request_info=resp.request_info,
                history=resp.history,
                status=404,
            )
        elif "500" in url:
            resp = MockResponse("Server Error", status=500)
            raise aiohttp.ClientResponseError(
                request_info=resp.request_info,
                history=resp.history,
                status=500,
            )
        return MockResponse(TECHCRUNCH_RSS, status=200)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            # Should only get items from successful feed
            assert all(item.source == "Good Feed" for item in items)
            assert len(items) == 2  # From TechCrunch sample


@pytest.mark.asyncio
async def test_collector_validates_required_fields():
    """Should skip items missing required fields"""

    from datetime import UTC, datetime, timedelta

    # Use recent dates
    recent_date = datetime.now(UTC) - timedelta(days=1)
    date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    # RSS with some items missing required fields
    invalid_rss = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <item>
                <title>Valid Article</title>
                <link>https://example.com/valid</link>
                <pubDate>{date_str}</pubDate>
            </item>
            <item>
                <!-- Missing title -->
                <link>https://example.com/no-title</link>
                <pubDate>{date_str}</pubDate>
            </item>
            <item>
                <title>No Link Article</title>
                <!-- Missing link -->
                <pubDate>{date_str}</pubDate>
            </item>
        </channel>
    </rss>"""

    feeds_config = [{"url": "https://example.com/feed", "name": "Test Feed"}]

    async def mock_request(self, method, url, **kwargs):
        return MockResponse(invalid_rss)

    with patch.object(settings, "rss_feeds", feeds_config):
        with patch("aiohttp.ClientSession._request", mock_request):
            collector = RSSCollector()
            items = await collector.collect()

            # Should only get the valid item
            assert len(items) == 1
            assert items[0].title == "Valid Article"
