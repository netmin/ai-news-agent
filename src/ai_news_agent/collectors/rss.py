"""RSS feed collector with concurrent fetching and retry logic"""

import asyncio
import time
from datetime import UTC, datetime, timedelta

import aiohttp
from loguru import logger

from ..config import settings
from ..models import CollectorStats, NewsItem
from ..utils.rate_limiter import ConcurrencyLimiter, RateLimiter
from .base import BaseCollector
from .parsers import ArxivParser, StandardParser


class RSSCollector(BaseCollector):
    """Collector for RSS feeds with concurrent fetching

    Features:
    - Concurrent fetching from multiple feeds
    - Exponential backoff retry logic
    - Feed-specific parsers (ArXiv special handling)
    - Performance statistics tracking
    - Graceful error handling
    - Deduplication within batch
    """

    def __init__(self):
        """Initialize RSS collector with statistics tracking"""
        self.stats: dict[str, CollectorStats] = {}
        self._init_stats()

        # Rate limiting: 2 requests per second per domain, burst of 5
        self.rate_limiter = RateLimiter(rate=2.0, burst=5, per_domain=True)

        # Concurrency limiting: max 3 concurrent connections per domain
        self.concurrency_limiter = ConcurrencyLimiter(max_concurrent=3)

    def _init_stats(self) -> None:
        """Initialize statistics for all configured feeds"""
        for feed in settings.rss_feeds:
            self.stats[feed["name"]] = CollectorStats(source=feed["name"])

    async def collect(self) -> list[NewsItem]:
        """Collect news items from all configured RSS feeds

        Returns:
            List of deduplicated NewsItem objects from all feeds
        """
        logger.info(f"Starting RSS collection from {len(settings.rss_feeds)} feeds")

        # Create tasks for concurrent fetching
        tasks = []
        async with aiohttp.ClientSession() as session:
            for feed in settings.rss_feeds:
                task = self._fetch_feed(session, feed)
                tasks.append(task)

            # Gather results concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine and deduplicate results
        all_items: list[NewsItem] = []
        seen_ids: set[str] = set()

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Feed collection error: {result}")
                continue

            if result:
                for item in result:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        all_items.append(item)

        # Filter old articles
        cutoff_date = datetime.now(UTC) - timedelta(days=settings.max_age_days)
        filtered_items = [
            item
            for item in all_items
            if item.published_at.replace(tzinfo=UTC) > cutoff_date
        ]

        logger.info(
            f"Collected {len(filtered_items)} unique items "
            f"({len(all_items) - len(filtered_items)} filtered as too old)"
        )

        return filtered_items

    async def _fetch_feed(
        self, session: aiohttp.ClientSession, feed_config: dict[str, str]
    ) -> list[NewsItem]:
        """Fetch and parse a single RSS feed with retry logic

        Args:
            session: aiohttp client session
            feed_config: Feed configuration with url and name

        Returns:
            List of NewsItem objects from the feed
        """
        url = feed_config["url"]
        name = feed_config["name"]
        stats = self.stats[name]

        start_time = time.time()

        for attempt in range(settings.max_retries):
            try:
                # Create timeout
                timeout = aiohttp.ClientTimeout(total=settings.request_timeout)

                # Fetch RSS content
                logger.debug(f"Fetching {name} (attempt {attempt + 1})")

                # Apply rate limiting
                await self.rate_limiter.acquire(url)

                # Apply concurrency limiting
                semaphore = await self.concurrency_limiter.acquire(url)
                async with semaphore:
                    async with session.get(url, timeout=timeout) as response:
                        if response.status != 200:
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=response.status,
                            )

                        content = await response.text()

                # Parse content with appropriate parser
                parser = self._get_parser(name)
                items = await parser.parse(content)

                # Update success statistics
                elapsed = time.time() - start_time
                stats.success_count += 1
                stats.last_success = datetime.now(UTC)
                stats.average_response_time = (
                    stats.average_response_time * (stats.success_count - 1) + elapsed
                ) / stats.success_count
                stats.average_items = (
                    stats.average_items * (stats.success_count - 1) + len(items)
                ) / stats.success_count

                logger.info(
                    f"Successfully fetched {len(items)} items from {name} "
                    f"in {elapsed:.2f}s"
                )

                return items

            except TimeoutError:
                logger.warning(f"Timeout fetching {name} (attempt {attempt + 1})")

            except aiohttp.ClientError as e:
                logger.warning(f"Network error fetching {name}: {e}")

            except Exception as e:
                logger.error(f"Unexpected error fetching {name}: {e}")

            # Exponential backoff before retry
            if attempt < settings.max_retries - 1:
                delay = settings.retry_delay * (2**attempt)
                logger.debug(f"Retrying {name} after {delay:.1f}s")
                await asyncio.sleep(delay)

        # Update failure statistics
        stats.failure_count += 1
        stats.last_failure = datetime.now(UTC)

        logger.error(f"Failed to fetch {name} after {settings.max_retries} attempts")

        return []

    def _get_parser(self, feed_name: str) -> StandardParser | ArxivParser:
        """Get appropriate parser for the feed

        Args:
            feed_name: Name of the RSS feed

        Returns:
            Parser instance for the feed type
        """
        if "arxiv" in feed_name.lower():
            return ArxivParser(feed_name)
        else:
            return StandardParser(feed_name)

    async def get_stats(self) -> list[CollectorStats]:
        """Get performance statistics for all feeds

        Returns:
            List of CollectorStats objects
        """
        return list(self.stats.values())
