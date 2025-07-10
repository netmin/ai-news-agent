"""Integration test for RSS collector with real parsing"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from ai_news_agent.collectors.rss import RSSCollector
from ai_news_agent.config import settings


@pytest.mark.asyncio
async def test_collector_full_integration():
    """Test RSS collector end-to-end with mocked HTTP responses"""

    # Use recent dates that will always be within max_age_days
    recent_date = datetime.now(UTC) - timedelta(days=1)
    date1_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
    date2_str = (recent_date + timedelta(hours=1)).strftime("%a, %d %b %Y %H:%M:%S GMT")

    # Create test RSS content with dynamic dates
    test_rss = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <item>
                <title>Test Article 1</title>
                <link>https://example.com/article1</link>
                <description>This is test article 1</description>
                <pubDate>{date1_str}</pubDate>
            </item>
            <item>
                <title>Test Article 2</title>
                <link>https://example.com/article2</link>
                <description>This is test article 2</description>
                <pubDate>{date2_str}</pubDate>
            </item>
        </channel>
    </rss>"""

    # Mock only the HTTP request part
    async def mock_fetch(self, method, url, **kwargs):
        # Create a mock response object
        class MockResp:
            status = 200

            async def text(self):
                return test_rss

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        return MockResp()

    # Configure single feed for testing
    test_feeds = [{"url": "https://example.com/feed", "name": "Test Feed"}]

    with patch.object(settings, "rss_feeds", test_feeds):
        with patch("aiohttp.ClientSession._request", mock_fetch):
            collector = RSSCollector()
            items = await collector.collect()

            # Verify results
            assert len(items) == 2
            assert items[0].title == "Test Article 1"
            assert items[1].title == "Test Article 2"
            assert all(item.source == "Test Feed" for item in items)
            assert all(item.id is not None for item in items)

            # Check statistics
            stats = await collector.get_stats()
            assert len(stats) == 1
            assert stats[0].source == "Test Feed"
            assert stats[0].success_count == 1
            assert stats[0].failure_count == 0
            assert stats[0].success_rate == 1.0


@pytest.mark.asyncio
async def test_collector_error_handling():
    """Test RSS collector handles errors gracefully"""

    # Mock HTTP error
    async def mock_fetch_error(self, method, url, **kwargs):
        raise Exception("Network error")

    test_feeds = [
        {"url": "https://example.com/bad", "name": "Bad Feed"},
        {"url": "https://example.com/good", "name": "Good Feed"},
    ]

    # Use recent date
    recent_date = datetime.now(UTC) - timedelta(days=1)
    date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    good_rss = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Good Feed</title>
            <item>
                <title>Good Article</title>
                <link>https://example.com/good-article</link>
                <pubDate>{date_str}</pubDate>
            </item>
        </channel>
    </rss>"""

    async def mock_fetch_mixed(self, method, url, **kwargs):
        if "bad" in url:
            raise Exception("Network error")

        class MockResp:
            status = 200

            async def text(self):
                return good_rss

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        return MockResp()

    with patch.object(settings, "rss_feeds", test_feeds):
        with patch("aiohttp.ClientSession._request", mock_fetch_mixed):
            collector = RSSCollector()
            items = await collector.collect()

            # Should get items only from good feed
            assert len(items) == 1
            assert items[0].title == "Good Article"
            assert items[0].source == "Good Feed"

            # Check statistics show failure
            stats = await collector.get_stats()
            bad_stats = next(s for s in stats if s.source == "Bad Feed")
            good_stats = next(s for s in stats if s.source == "Good Feed")

            assert bad_stats.failure_count > 0
            assert bad_stats.success_count == 0
            assert good_stats.success_count == 1
            assert good_stats.failure_count == 0
