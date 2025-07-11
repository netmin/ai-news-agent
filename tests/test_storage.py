"""Tests for the storage module."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_news_agent.models import CollectorStats, NewsItem
from ai_news_agent.storage import (
    CollectorRepository,
    DatabaseManager,
    DigestRepository,
    NewsItemRepository,
)
from ai_news_agent.storage.models import NewsItemDB


@pytest.fixture
async def db_manager():
    """Create a test database manager."""
    # Use in-memory SQLite for tests
    manager = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await manager.init_db()
    yield manager
    await manager.close()


@pytest.fixture
async def db_session(db_manager):
    """Get a test database session."""
    async with db_manager.get_session() as session:
        yield session


@pytest.fixture
def sample_news_item():
    """Create a sample news item."""
    return NewsItem(
        url="https://example.com/article1",
        title="Test Article",
        content="This is the full content of the test article.",
        summary="Test summary",
        source="Test Source",
        published_at=datetime.now(timezone.utc),
        tags=["ai", "test"],
        metadata={"author": "Test Author"},
    )


class TestDatabaseManager:
    """Test DatabaseManager functionality."""

    @pytest.mark.asyncio
    async def test_init_db(self, db_manager):
        """Test database initialization."""
        # Tables should be created
        assert await db_manager.health_check()

    @pytest.mark.asyncio
    async def test_get_session(self, db_manager):
        """Test getting a database session."""
        async with db_manager.get_session() as session:
            assert isinstance(session, AsyncSession)
            # Test a simple query
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_health_check(self, db_manager):
        """Test database health check."""
        assert await db_manager.health_check() is True


class TestNewsItemRepository:
    """Test NewsItemRepository functionality."""

    @pytest.mark.asyncio
    async def test_create_news_item(self, db_session, sample_news_item):
        """Test creating a news item."""
        repo = NewsItemRepository(db_session)
        
        db_item = await repo.create(sample_news_item)
        await db_session.commit()
        
        assert db_item.id == sample_news_item.id
        assert db_item.title == sample_news_item.title
        assert db_item.url == str(sample_news_item.url)

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session, sample_news_item):
        """Test getting news item by ID."""
        repo = NewsItemRepository(db_session)
        
        # Create item
        await repo.create(sample_news_item)
        await db_session.commit()
        
        # Retrieve by ID
        found = await repo.get_by_id(sample_news_item.id)
        assert found is not None
        assert found.id == sample_news_item.id

    @pytest.mark.asyncio
    async def test_get_by_url(self, db_session, sample_news_item):
        """Test getting news item by URL."""
        repo = NewsItemRepository(db_session)
        
        # Create item
        await repo.create(sample_news_item)
        await db_session.commit()
        
        # Retrieve by URL
        found = await repo.get_by_url(str(sample_news_item.url))
        assert found is not None
        assert found.url == str(sample_news_item.url)

    @pytest.mark.asyncio
    async def test_find_duplicates(self, db_session, sample_news_item):
        """Test finding duplicate items."""
        repo = NewsItemRepository(db_session)
        
        # Create original item
        await repo.create(sample_news_item)
        await db_session.commit()
        
        # Find duplicates by URL
        duplicates = await repo.find_duplicates(
            str(sample_news_item.url),
            "Different Title"
        )
        assert len(duplicates) == 1
        assert duplicates[0].id == sample_news_item.id
        
        # Find duplicates by title
        duplicates = await repo.find_duplicates(
            "https://different.com",
            sample_news_item.title
        )
        assert len(duplicates) == 1

    @pytest.mark.asyncio
    async def test_get_recent(self, db_session):
        """Test getting recent news items."""
        repo = NewsItemRepository(db_session)
        
        # Create items with different dates
        now = datetime.now(timezone.utc)
        for i in range(5):
            item = NewsItem(
                url=f"https://example.com/article{i}",
                title=f"Article {i}",
                content=f"Content {i}",
                source="Test Source",
                published_at=now - timedelta(days=i),
            )
            await repo.create(item)
        await db_session.commit()
        
        # Get recent items (last 3 days)
        recent = await repo.get_recent(days=3)
        assert len(recent) == 3
        # Should be ordered by published_at desc
        assert recent[0].title == "Article 0"

    @pytest.mark.asyncio
    async def test_mark_as_duplicate(self, db_session):
        """Test marking item as duplicate."""
        repo = NewsItemRepository(db_session)
        
        # Create two items
        item1 = NewsItem(
            url="https://example.com/original",
            title="Original Article",
            content="Original content",
            source="Test Source",
            published_at=datetime.now(timezone.utc),
        )
        item2 = NewsItem(
            url="https://example.com/duplicate",
            title="Duplicate Article",
            content="Duplicate content",
            source="Test Source",
            published_at=datetime.now(timezone.utc),
        )
        
        db_item1 = await repo.create(item1)
        db_item2 = await repo.create(item2)
        await db_session.commit()
        
        # Mark item2 as duplicate of item1
        updated = await repo.mark_as_duplicate(item2.id, item1.id)
        await db_session.commit()
        
        assert updated is not None
        assert updated.is_duplicate is True
        assert updated.duplicate_of == item1.id

    @pytest.mark.asyncio
    async def test_count_by_source(self, db_session):
        """Test counting items by source."""
        repo = NewsItemRepository(db_session)
        
        # Create items from different sources
        sources = ["TechCrunch", "ArXiv", "TechCrunch", "OpenAI"]
        for i, source in enumerate(sources):
            item = NewsItem(
                url=f"https://example.com/article{i}",
                title=f"Article {i}",
                content=f"Content {i}",
                source=source,
                published_at=datetime.now(timezone.utc),
            )
            await repo.create(item)
        await db_session.commit()
        
        # Count by source
        counts = await repo.count_by_source()
        counts_dict = dict(counts)
        
        assert counts_dict["TechCrunch"] == 2
        assert counts_dict["ArXiv"] == 1
        assert counts_dict["OpenAI"] == 1


class TestCollectorRepository:
    """Test CollectorRepository functionality."""

    @pytest.mark.asyncio
    async def test_create_run(self, db_session):
        """Test creating a collector run."""
        repo = CollectorRepository(db_session)
        
        run = await repo.create_run("rss", {"initial": "stats"})
        await db_session.commit()
        
        assert run.id is not None
        assert run.collector_type == "rss"
        assert run.statistics == {"initial": "stats"}
        assert run.started_at is not None
        assert run.completed_at is None

    @pytest.mark.asyncio
    async def test_complete_run(self, db_session):
        """Test completing a collector run."""
        repo = CollectorRepository(db_session)
        
        # Create run
        run = await repo.create_run("rss")
        await db_session.commit()
        
        # Complete run
        updated = await repo.complete_run(
            run.id,
            total_items=10,
            new_items=8,
            duplicate_items=2,
            failed_sources=["source1"],
            statistics={"final": "stats"},
        )
        await db_session.commit()
        
        assert updated is not None
        assert updated.total_items == 10
        assert updated.new_items == 8
        assert updated.duplicate_items == 2
        assert updated.failed_sources == ["source1"]
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_link_items_to_run(self, db_session, sample_news_item):
        """Test linking news items to a collector run."""
        news_repo = NewsItemRepository(db_session)
        collector_repo = CollectorRepository(db_session)
        
        # Create news item and run
        db_item = await news_repo.create(sample_news_item)
        run = await collector_repo.create_run("rss")
        await db_session.commit()
        
        # Link item to run
        await collector_repo.link_items_to_run(run.id, [db_item.id])
        await db_session.commit()
        
        # Verify link (would need to query the association table)
        # For now, just check no errors

    @pytest.mark.asyncio
    async def test_get_collector_stats(self, db_session):
        """Test getting collector statistics."""
        repo = CollectorRepository(db_session)
        
        # Create some runs
        for i in range(3):
            run = await repo.create_run("rss")
            await repo.complete_run(
                run.id,
                total_items=10 + i,
                new_items=8,
                duplicate_items=2,
                failed_sources=[],
                statistics={},
            )
        await db_session.commit()
        
        # Get stats
        stats = await repo.get_collector_stats("rss", days=7)
        
        assert stats.source == "rss"
        assert stats.success_count == 3
        assert stats.failure_count == 0
        assert stats.average_items == 11.0  # (10 + 11 + 12) / 3
        assert stats.success_rate == 1.0
        assert stats.last_success is not None


class TestDigestRepository:
    """Test DigestRepository functionality."""

    @pytest.mark.asyncio
    async def test_create_daily_digest(self, db_session, sample_news_item):
        """Test creating a daily digest."""
        news_repo = NewsItemRepository(db_session)
        digest_repo = DigestRepository(db_session)
        
        # Create news items
        db_item = await news_repo.create(sample_news_item)
        await db_session.commit()
        
        # Create digest
        digest_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        digest = await digest_repo.create_daily_digest(digest_date, [db_item])
        await db_session.commit()
        
        assert digest.id is not None
        assert digest.date == digest_date
        assert digest.item_count == 1
        assert digest.is_sent is False

    @pytest.mark.asyncio
    async def test_get_daily_digest(self, db_session, sample_news_item):
        """Test getting a daily digest by date."""
        news_repo = NewsItemRepository(db_session)
        digest_repo = DigestRepository(db_session)
        
        # Create digest
        db_item = await news_repo.create(sample_news_item)
        digest_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        await digest_repo.create_daily_digest(digest_date, [db_item])
        await db_session.commit()
        
        # Get digest
        found = await digest_repo.get_daily_digest(digest_date)
        assert found is not None
        # SQLite doesn't preserve timezone info, so compare without tz
        assert found.date.replace(tzinfo=timezone.utc) == digest_date

    @pytest.mark.asyncio
    async def test_create_weekly_summary(self, db_session, sample_news_item):
        """Test creating a weekly summary."""
        news_repo = NewsItemRepository(db_session)
        digest_repo = DigestRepository(db_session)
        
        # Create news items
        db_item = await news_repo.create(sample_news_item)
        await db_session.commit()
        
        # Create summary
        week_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=6)
        
        summary = await digest_repo.create_weekly_summary(
            week_start,
            week_end,
            [db_item],
            ["AI", "Technology"],
        )
        await db_session.commit()
        
        assert summary.id is not None
        assert summary.week_start == week_start
        assert summary.week_end == week_end
        assert summary.item_count == 1
        assert summary.top_topics == ["AI", "Technology"]

    @pytest.mark.asyncio
    async def test_get_unsent_digests(self, db_session, sample_news_item):
        """Test getting unsent digests."""
        news_repo = NewsItemRepository(db_session)
        digest_repo = DigestRepository(db_session)
        
        # Create items
        db_item = await news_repo.create(sample_news_item)
        
        # Create unsent daily digest
        digest_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        daily = await digest_repo.create_daily_digest(digest_date, [db_item])
        
        # Create unsent weekly summary
        week_start = digest_date - timedelta(days=7)
        week_end = digest_date - timedelta(days=1)
        weekly = await digest_repo.create_weekly_summary(
            week_start,
            week_end,
            [db_item],
            ["AI"],
        )
        await db_session.commit()
        
        # Get unsent
        daily_unsent, weekly_unsent = await digest_repo.get_unsent_digests()
        
        assert len(daily_unsent) == 1
        assert len(weekly_unsent) == 1
        assert daily_unsent[0].id == daily.id
        assert weekly_unsent[0].id == weekly.id

    @pytest.mark.asyncio
    async def test_mark_digest_sent(self, db_session, sample_news_item):
        """Test marking digest as sent."""
        news_repo = NewsItemRepository(db_session)
        digest_repo = DigestRepository(db_session)
        
        # Create digest
        db_item = await news_repo.create(sample_news_item)
        digest_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        digest = await digest_repo.create_daily_digest(digest_date, [db_item])
        await db_session.commit()
        
        # Mark as sent
        await digest_repo.mark_digest_sent(digest)
        await db_session.commit()
        
        # Verify
        assert digest.is_sent is True
        assert digest.sent_at is not None