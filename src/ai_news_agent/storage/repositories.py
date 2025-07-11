"""Repository pattern implementations for database operations."""

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CollectorStats, NewsItem
from .models import (
    CollectorRunDB,
    DailyDigestDB,
    DeduplicationCacheDB,
    DigestEntryDB,
    NewsItemDB,
    WeeklySummaryDB,
    collector_run_items,
)


class NewsItemRepository:
    """Repository for NewsItem database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: AsyncSession instance
        """
        self.session = session

    async def create(self, news_item: NewsItem) -> NewsItemDB:
        """Create a news item in the database.

        Args:
            news_item: NewsItem to persist

        Returns:
            NewsItemDB: Created database record
        """
        db_item = NewsItemDB(
            id=news_item.id,
            url=str(news_item.url),
            title=news_item.title,
            content=news_item.content,
            summary=news_item.summary,
            source=news_item.source,
            published_at=news_item.published_at,
            collected_at=news_item.collected_at,
            tags=news_item.tags,
            extra_metadata=news_item.metadata,
        )
        self.session.add(db_item)
        await self.session.flush()
        return db_item

    async def get_by_id(self, item_id: str) -> NewsItemDB | None:
        """Get news item by ID.

        Args:
            item_id: News item ID (SHA256 hash)

        Returns:
            Optional[NewsItemDB]: Found item or None
        """
        result = await self.session.execute(
            select(NewsItemDB).where(NewsItemDB.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> NewsItemDB | None:
        """Get news item by URL.

        Args:
            url: News item URL

        Returns:
            Optional[NewsItemDB]: Found item or None
        """
        result = await self.session.execute(
            select(NewsItemDB).where(NewsItemDB.url == url)
        )
        return result.scalar_one_or_none()

    async def find_duplicates(
        self, url: str, title: str, lookback_days: int = 7
    ) -> list[NewsItemDB]:
        """Find potential duplicate items.

        Args:
            url: URL to check
            title: Title to check
            lookback_days: How many days back to search

        Returns:
            List[NewsItemDB]: Potential duplicates
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=lookback_days)

        # Check exact URL match or similar title
        result = await self.session.execute(
            select(NewsItemDB).where(
                and_(
                    NewsItemDB.collected_at >= cutoff_date,
                    or_(
                        NewsItemDB.url == url,
                        func.lower(NewsItemDB.title) == func.lower(title),
                    ),
                )
            )
        )
        return list(result.scalars().all())

    async def get_recent(
        self,
        days: int = 7,
        source: str | None = None,
        limit: int | None = None,
    ) -> list[NewsItemDB]:
        """Get recent news items.

        Args:
            days: Number of days to look back
            source: Filter by source (optional)
            limit: Maximum number of items to return

        Returns:
            List[NewsItemDB]: Recent news items
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        query = select(NewsItemDB).where(
            and_(
                NewsItemDB.published_at >= cutoff_date,
                NewsItemDB.is_duplicate == False,
            )
        )

        if source:
            query = query.where(NewsItemDB.source == source)

        query = query.order_by(desc(NewsItemDB.published_at))

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def mark_as_duplicate(
        self, item_id: str, duplicate_of: str
    ) -> NewsItemDB | None:
        """Mark an item as duplicate.

        Args:
            item_id: ID of the duplicate item
            duplicate_of: ID of the original item

        Returns:
            Optional[NewsItemDB]: Updated item or None
        """
        item = await self.get_by_id(item_id)
        if item:
            item.is_duplicate = True
            item.duplicate_of = duplicate_of
            await self.session.flush()
        return item

    async def count_by_source(
        self, start_date: datetime | None = None
    ) -> list[tuple[str, int]]:
        """Count news items by source.

        Args:
            start_date: Count items after this date

        Returns:
            List[Tuple[str, int]]: List of (source, count) tuples
        """
        query = (
            select(NewsItemDB.source, func.count(NewsItemDB.id))
            .where(NewsItemDB.is_duplicate == False)
            .group_by(NewsItemDB.source)
        )

        if start_date:
            query = query.where(NewsItemDB.collected_at >= start_date)

        result = await self.session.execute(query)
        return list(result.all())


class CollectorRepository:
    """Repository for collector run operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: AsyncSession instance
        """
        self.session = session

    async def create_run(
        self, collector_type: str, stats: dict | None = None
    ) -> CollectorRunDB:
        """Create a new collector run record.

        Args:
            collector_type: Type of collector (e.g., "rss")
            stats: Initial statistics

        Returns:
            CollectorRunDB: Created collector run
        """
        run = CollectorRunDB(
            collector_type=collector_type,
            started_at=datetime.now(UTC),
            statistics=stats or {},
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def complete_run(
        self,
        run_id: int,
        total_items: int,
        new_items: int,
        duplicate_items: int,
        failed_sources: list[str],
        statistics: dict,
    ) -> CollectorRunDB | None:
        """Complete a collector run with final statistics.

        Args:
            run_id: Collector run ID
            total_items: Total items collected
            new_items: New items added
            duplicate_items: Duplicate items found
            failed_sources: List of failed sources
            statistics: Final statistics

        Returns:
            Optional[CollectorRunDB]: Updated run or None
        """
        result = await self.session.execute(
            select(CollectorRunDB).where(CollectorRunDB.id == run_id)
        )
        run = result.scalar_one_or_none()

        if run:
            run.completed_at = datetime.now(UTC)
            run.total_items = total_items
            run.new_items = new_items
            run.duplicate_items = duplicate_items
            run.failed_sources = failed_sources
            run.statistics = statistics
            await self.session.flush()

        return run

    async def link_items_to_run(
        self, run_id: int, item_ids: list[str]
    ) -> None:
        """Link news items to a collector run.

        Args:
            run_id: Collector run ID
            item_ids: List of news item IDs
        """
        for item_id in item_ids:
            await self.session.execute(
                collector_run_items.insert().values(
                    collector_run_id=run_id, news_item_id=item_id
                )
            )
        await self.session.flush()

    async def get_recent_runs(
        self, collector_type: str | None = None, limit: int = 10
    ) -> list[CollectorRunDB]:
        """Get recent collector runs.

        Args:
            collector_type: Filter by collector type
            limit: Maximum number of runs to return

        Returns:
            List[CollectorRunDB]: Recent collector runs
        """
        query = select(CollectorRunDB).order_by(desc(CollectorRunDB.started_at))

        if collector_type:
            query = query.where(CollectorRunDB.collector_type == collector_type)

        query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_collector_stats(
        self, collector_type: str, days: int = 7
    ) -> CollectorStats:
        """Get collector statistics for the past N days.

        Args:
            collector_type: Type of collector
            days: Number of days to analyze

        Returns:
            CollectorStats: Aggregated statistics
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        # Get all runs in the period
        result = await self.session.execute(
            select(CollectorRunDB).where(
                and_(
                    CollectorRunDB.collector_type == collector_type,
                    CollectorRunDB.started_at >= cutoff_date,
                )
            )
        )
        runs = list(result.scalars().all())

        if not runs:
            return CollectorStats(
                source=collector_type,
                total_collected=0,
                success_rate=0.0,
                average_fetch_time=0.0,
                last_collected=None,
            )

        # Calculate statistics
        total_collected = sum(run.total_items for run in runs)
        completed_runs = [run for run in runs if run.completed_at]
        success_rate = len(completed_runs) / len(runs) if runs else 0.0

        # Calculate average fetch time
        fetch_times = []
        for run in completed_runs:
            if run.completed_at and run.started_at:
                fetch_time = (run.completed_at - run.started_at).total_seconds()
                fetch_times.append(fetch_time)

        average_fetch_time = sum(fetch_times) / len(fetch_times) if fetch_times else 0.0

        # Get last collection time
        # Handle timezone-naive datetimes from SQLite
        def get_started_at(run):
            if run.started_at.tzinfo is None:
                return run.started_at.replace(tzinfo=UTC)
            return run.started_at

        last_run = max(runs, key=get_started_at)
        last_collected = last_run.started_at

        return CollectorStats(
            source=collector_type,
            success_count=len(completed_runs),
            failure_count=len(runs) - len(completed_runs),
            last_success=last_collected if completed_runs else None,
            last_failure=None,  # Could track failed runs separately
            average_items=total_collected / len(runs) if runs else 0.0,
            average_response_time=average_fetch_time,
        )


class DigestRepository:
    """Repository for digest operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: AsyncSession instance
        """
        self.session = session

    async def create_daily_digest(
        self, date: datetime, items: list[NewsItemDB]
    ) -> DailyDigestDB:
        """Create a daily digest.

        Args:
            date: Date of the digest
            items: News items to include

        Returns:
            DailyDigestDB: Created digest
        """
        digest = DailyDigestDB(
            date=date,
            item_count=len(items),
        )
        self.session.add(digest)
        await self.session.flush()

        # Create digest entries
        for idx, item in enumerate(items):
            entry = DigestEntryDB(
                news_item_id=item.id,
                daily_digest_id=digest.id,
                ranking_score=float(len(items) - idx),  # Higher score for earlier items
            )
            self.session.add(entry)

        await self.session.flush()
        return digest

    async def get_daily_digest(self, date: datetime) -> DailyDigestDB | None:
        """Get daily digest for a specific date.

        Args:
            date: Date to get digest for

        Returns:
            Optional[DailyDigestDB]: Found digest or None
        """
        result = await self.session.execute(
            select(DailyDigestDB).where(DailyDigestDB.date == date)
        )
        return result.scalar_one_or_none()

    async def create_weekly_summary(
        self,
        week_start: datetime,
        week_end: datetime,
        items: list[NewsItemDB],
        top_topics: list[str],
    ) -> WeeklySummaryDB:
        """Create a weekly summary.

        Args:
            week_start: Start date of the week
            week_end: End date of the week
            items: News items to include
            top_topics: Top topics for the week

        Returns:
            WeeklySummaryDB: Created summary
        """
        summary = WeeklySummaryDB(
            week_start=week_start,
            week_end=week_end,
            item_count=len(items),
            top_topics=top_topics,
        )
        self.session.add(summary)
        await self.session.flush()

        # Create summary entries
        for idx, item in enumerate(items):
            entry = DigestEntryDB(
                news_item_id=item.id,
                weekly_summary_id=summary.id,
                ranking_score=float(len(items) - idx),
            )
            self.session.add(entry)

        await self.session.flush()
        return summary

    async def get_weekly_summary(
        self, week_start: datetime
    ) -> WeeklySummaryDB | None:
        """Get weekly summary for a specific week.

        Args:
            week_start: Start date of the week

        Returns:
            Optional[WeeklySummaryDB]: Found summary or None
        """
        result = await self.session.execute(
            select(WeeklySummaryDB).where(WeeklySummaryDB.week_start == week_start)
        )
        return result.scalar_one_or_none()

    async def get_unsent_digests(self) -> tuple[list[DailyDigestDB], list[WeeklySummaryDB]]:
        """Get all unsent digests and summaries.

        Returns:
            Tuple[List[DailyDigestDB], List[WeeklySummaryDB]]: Unsent digests and summaries
        """
        # Get unsent daily digests
        daily_result = await self.session.execute(
            select(DailyDigestDB).where(DailyDigestDB.is_sent == False)
        )
        daily_digests = list(daily_result.scalars().all())

        # Get unsent weekly summaries
        weekly_result = await self.session.execute(
            select(WeeklySummaryDB).where(WeeklySummaryDB.is_sent == False)
        )
        weekly_summaries = list(weekly_result.scalars().all())

        return daily_digests, weekly_summaries

    async def mark_digest_sent(
        self, digest: DailyDigestDB | WeeklySummaryDB
    ) -> None:
        """Mark a digest or summary as sent.

        Args:
            digest: Digest or summary to mark as sent
        """
        digest.is_sent = True
        digest.sent_at = datetime.now(UTC)
        await self.session.flush()


class DeduplicationRepository:
    """Repository for deduplication operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: AsyncSession instance
        """
        self.session = session

    @staticmethod
    def _hash_text(text: str) -> str:
        """Create SHA256 hash of text.

        Args:
            text: Text to hash

        Returns:
            str: Hex digest of hash
        """
        return hashlib.sha256(text.encode()).hexdigest()

    async def add_to_cache(self, news_item: NewsItemDB) -> DeduplicationCacheDB:
        """Add item to deduplication cache.

        Args:
            news_item: News item to cache

        Returns:
            DeduplicationCacheDB: Created cache entry
        """
        url_hash = self._hash_text(news_item.url)
        title_hash = self._hash_text(news_item.title.lower())
        content_hash = self._hash_text(news_item.content[:500].lower())  # First 500 chars

        # Check if already exists
        result = await self.session.execute(
            select(DeduplicationCacheDB).where(
                DeduplicationCacheDB.url_hash == url_hash
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.last_seen_at = datetime.now(UTC)
            existing.occurrence_count += 1
            return existing

        # Create new cache entry
        cache_entry = DeduplicationCacheDB(
            url_hash=url_hash,
            title_hash=title_hash,
            content_hash=content_hash,
            news_item_id=news_item.id,
        )
        self.session.add(cache_entry)
        await self.session.flush()
        return cache_entry

    async def find_similar(
        self, url: str, title: str, content: str, threshold: float = 0.85
    ) -> DeduplicationCacheDB | None:
        """Find similar items in cache.

        Args:
            url: URL to check
            title: Title to check
            content: Content to check
            threshold: Similarity threshold (not used for exact matching)

        Returns:
            Optional[DeduplicationCacheDB]: Similar item if found
        """
        url_hash = self._hash_text(url)
        title_hash = self._hash_text(title.lower())
        content_hash = self._hash_text(content[:500].lower())

        # Check for exact matches
        result = await self.session.execute(
            select(DeduplicationCacheDB).where(
                or_(
                    DeduplicationCacheDB.url_hash == url_hash,
                    and_(
                        DeduplicationCacheDB.title_hash == title_hash,
                        DeduplicationCacheDB.content_hash == content_hash,
                    ),
                )
            )
        )
        return result.scalar_one_or_none()

    async def cleanup_old_entries(self, days: int = 30) -> int:
        """Remove old cache entries.

        Args:
            days: Remove entries older than this many days

        Returns:
            int: Number of entries removed
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        result = await self.session.execute(
            select(DeduplicationCacheDB).where(
                DeduplicationCacheDB.last_seen_at < cutoff_date
            )
        )
        old_entries = list(result.scalars().all())

        for entry in old_entries:
            await self.session.delete(entry)

        await self.session.flush()
        return len(old_entries)
