"""Tests for RSS collector with storage integration."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_news_agent.collectors.rss_with_storage import RSSCollectorWithStorage
from ai_news_agent.deduplication.service import DuplicateMatch
from ai_news_agent.models import NewsItem
from ai_news_agent.storage.models import CollectorRunDB, NewsItemDB


@pytest.fixture
def sample_news_items():
    """Create sample news items for testing."""
    base_time = datetime.now(UTC)
    
    return [
        NewsItem(
            url="https://example.com/article1",
            title="AI Breakthrough in Natural Language Processing",
            content="Researchers have developed a new model that improves NLP accuracy...",
            summary="New NLP model shows significant improvements",
            source="TechNews",
            published_at=base_time - timedelta(hours=2),
            collected_at=base_time,
            tags=["ai", "nlp"],
            metadata={"author": "John Doe"},
        ),
        NewsItem(
            url="https://example.com/article2",
            title="Machine Learning in Healthcare",
            content="Healthcare providers are adopting ML for diagnosis...",
            source="HealthTech",
            published_at=base_time - timedelta(hours=5),
            collected_at=base_time,
            tags=["ml", "healthcare"],
            metadata={},
        ),
        NewsItem(
            url="https://example.com/duplicate",
            title="AI Breakthrough in Natural Language Processing", # Duplicate title
            content="This is a duplicate article from another source...",
            source="AIDaily",
            published_at=base_time - timedelta(hours=3),
            collected_at=base_time,
            tags=["ai"],
            metadata={},
        ),
    ]


@pytest.fixture
def mock_db_items(sample_news_items):
    """Create mock database items from sample news items."""
    db_items = []
    for item in sample_news_items:
        db_item = MagicMock(spec=NewsItemDB)
        db_item.id = item.id
        db_item.url = item.url
        db_item.title = item.title
        db_item.content = item.content
        db_item.summary = item.summary
        db_item.source = item.source
        db_item.published_at = item.published_at
        db_item.collected_at = item.collected_at
        db_item.tags = item.tags
        db_item.extra_metadata = item.metadata
        db_items.append(db_item)
    return db_items


class TestRSSCollectorWithStorage:
    """Test RSS collector with storage integration."""
    
    @pytest.mark.asyncio
    async def test_collect_and_store_success(self, sample_news_items):
        """Test successful collection and storage of items."""
        # Mock settings to avoid initialization issues
        with patch('ai_news_agent.collectors.rss.settings') as mock_settings:
            mock_settings.rss_feeds = []
            mock_settings.max_age_days = 7
            collector = RSSCollectorWithStorage()
        
        # Mock the parent collect method
        with patch.object(collector, 'collect', return_value=sample_news_items):
            # Mock deduplication service
            mock_dup_results = [
                DuplicateMatch(
                    is_duplicate=False,
                    original_id=None,
                    similarity_score=0.0,
                    match_type="none"
                ),
                DuplicateMatch(
                    is_duplicate=False,
                    original_id=None,
                    similarity_score=0.0,
                    match_type="none"
                ),
                DuplicateMatch(
                    is_duplicate=True,
                    original_id="existing_id",
                    similarity_score=1.0,
                    match_type="exact_title"
                ),
            ]
            with patch.object(collector.dedup_service, 'check_batch', return_value=mock_dup_results):
                with patch.object(collector.dedup_service, 'add_to_cache'):
                    # Mock database operations
                    with patch('ai_news_agent.collectors.rss_with_storage.get_db_manager') as mock_db:
                        mock_session = AsyncMock()
                        mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
                        
                        # Mock repositories
                        mock_news_repo = AsyncMock()
                        mock_collector_repo = AsyncMock()
                        mock_dedup_repo = AsyncMock()
                        
                        # Mock collector run
                        mock_run = MagicMock()
                        mock_run.id = 1
                        mock_collector_repo.create_run.return_value = mock_run
                        
                        # Mock news item creation
                        created_items = []
                        for item in sample_news_items[:2]:  # Only first two are new
                            db_item = MagicMock()
                            db_item.id = item.id
                            created_items.append(db_item)
                        mock_news_repo.create.side_effect = created_items
                        
                        # Mock stats
                        with patch.object(collector, 'get_stats', return_value=[]):
                            with patch('ai_news_agent.collectors.rss_with_storage.NewsItemRepository', return_value=mock_news_repo):
                                with patch('ai_news_agent.collectors.rss_with_storage.CollectorRepository', return_value=mock_collector_repo):
                                    with patch('ai_news_agent.collectors.rss_with_storage.DeduplicationRepository', return_value=mock_dedup_repo):
                                        new_items, stats = await collector.collect_and_store()
        
        # Verify results
        assert len(new_items) == 2  # Two new items
        assert stats["total"] == 3
        assert stats["new"] == 2
        assert stats["duplicates"] == 1
        assert stats["run_id"] == 1
        
        # Verify repository calls
        mock_collector_repo.create_run.assert_called_once_with("rss")
        assert mock_news_repo.create.call_count == 2
        mock_dedup_repo.add_to_cache.assert_called()
        mock_collector_repo.complete_run.assert_called_once()
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collect_and_store_no_items(self):
        """Test collection with no items returned."""
        # Mock settings to avoid initialization issues
        with patch('ai_news_agent.collectors.rss.settings') as mock_settings:
            mock_settings.rss_feeds = []
            mock_settings.max_age_days = 7
            collector = RSSCollectorWithStorage()
        
        # Mock empty collection
        with patch.object(collector, 'collect', return_value=[]):
            new_items, stats = await collector.collect_and_store()
        
        assert len(new_items) == 0
        assert stats["total"] == 0
        assert stats["new"] == 0
        assert stats["duplicates"] == 0
    
    @pytest.mark.asyncio
    async def test_collect_and_store_all_duplicates(self, sample_news_items):
        """Test collection where all items are duplicates."""
        with patch('ai_news_agent.collectors.rss.settings') as mock_settings:
            mock_settings.rss_feeds = []
            mock_settings.max_age_days = 7
            collector = RSSCollectorWithStorage()
        
        with patch.object(collector, 'collect', return_value=sample_news_items):
            # All items are duplicates
            mock_dup_results = [
                DuplicateMatch(
                    is_duplicate=True,
                    original_id=f"existing_{i}",
                    similarity_score=1.0,
                    match_type="exact_url"
                ) for i, _ in enumerate(sample_news_items)
            ]
            with patch.object(collector.dedup_service, 'check_batch', return_value=mock_dup_results):
                with patch('ai_news_agent.collectors.rss_with_storage.get_db_manager') as mock_db:
                    mock_session = AsyncMock()
                    mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
                    
                    mock_collector_repo = AsyncMock()
                    mock_run = MagicMock(id=1)
                    mock_collector_repo.create_run.return_value = mock_run
                    
                    with patch.object(collector, 'get_stats', return_value=[]):
                        with patch('ai_news_agent.collectors.rss_with_storage.NewsItemRepository'):
                            with patch('ai_news_agent.collectors.rss_with_storage.CollectorRepository', return_value=mock_collector_repo):
                                with patch('ai_news_agent.collectors.rss_with_storage.DeduplicationRepository'):
                                    new_items, stats = await collector.collect_and_store()
        
        assert len(new_items) == 0
        assert stats["total"] == 3
        assert stats["new"] == 0
        assert stats["duplicates"] == 3
    
    @pytest.mark.asyncio
    async def test_collect_and_store_with_errors(self, sample_news_items):
        """Test collection with processing errors."""
        with patch('ai_news_agent.collectors.rss.settings') as mock_settings:
            mock_settings.rss_feeds = []
            mock_settings.max_age_days = 7
            collector = RSSCollectorWithStorage()
        
        with patch.object(collector, 'collect', return_value=sample_news_items):
            mock_dup_results = [
                DuplicateMatch(
                    is_duplicate=False,
                    original_id=None,
                    similarity_score=0.0,
                    match_type="none"
                ) for _ in sample_news_items
            ]
            with patch.object(collector.dedup_service, 'check_batch', return_value=mock_dup_results):
                with patch('ai_news_agent.collectors.rss_with_storage.get_db_manager') as mock_db:
                    mock_session = AsyncMock()
                    mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
                    
                    mock_news_repo = AsyncMock()
                    mock_collector_repo = AsyncMock()
                    mock_run = MagicMock(id=1)
                    mock_collector_repo.create_run.return_value = mock_run
                    
                    # First item succeeds, second fails, third succeeds
                    async def create_side_effect(item):
                        if item.source == "HealthTech":
                            raise Exception("Database error")
                        db_item = MagicMock()
                        db_item.id = item.id
                        return db_item
                    
                    mock_news_repo.create.side_effect = create_side_effect
                    
                    with patch.object(collector, 'get_stats', return_value=[]):
                        with patch('ai_news_agent.collectors.rss_with_storage.NewsItemRepository', return_value=mock_news_repo):
                            with patch('ai_news_agent.collectors.rss_with_storage.CollectorRepository', return_value=mock_collector_repo):
                                mock_dedup_repo = AsyncMock()
                                with patch('ai_news_agent.collectors.rss_with_storage.DeduplicationRepository', return_value=mock_dedup_repo):
                                    with patch.object(collector.dedup_service, 'add_to_cache'):
                                        new_items, stats = await collector.collect_and_store()
        
        assert len(new_items) == 2  # Two successful
        assert "HealthTech" in stats["failed_sources"]  # Middle item failed
    
    @pytest.mark.asyncio
    async def test_cleanup_old_duplicates(self):
        """Test cleanup of old duplicate entries."""
        with patch('ai_news_agent.collectors.rss.settings') as mock_settings:
            mock_settings.rss_feeds = []
            mock_settings.max_age_days = 7
            collector = RSSCollectorWithStorage()
        
        mock_cleanup_stats = {
            "database_entries_removed": 50,
            "cache_files_removed": 10,
        }
        
        # Use AsyncMock for async method
        mock_cleanup = AsyncMock(return_value=mock_cleanup_stats)
        collector.dedup_service.cleanup_old_data = mock_cleanup
        collector.dedup_service.clear_memory_cache = MagicMock()
        
        stats = await collector.cleanup_old_duplicates(days=30)
        
        assert stats["database_entries_removed"] == 50
        assert stats["cache_files_removed"] == 10
        mock_cleanup.assert_called_once_with(30)
        collector.dedup_service.clear_memory_cache.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_recent_items(self, mock_db_items):
        """Test retrieving recent items from database."""
        with patch('ai_news_agent.collectors.rss.settings') as mock_settings:
            mock_settings.rss_feeds = []
            mock_settings.max_age_days = 7
            collector = RSSCollectorWithStorage()
        
        with patch('ai_news_agent.collectors.rss_with_storage.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            mock_news_repo = AsyncMock()
            mock_news_repo.get_recent.return_value = mock_db_items[:2]
            
            with patch('ai_news_agent.collectors.rss_with_storage.NewsItemRepository', return_value=mock_news_repo):
                items = await collector.get_recent_items(days=7, source="TechNews", limit=10)
        
        assert len(items) == 2
        assert all(isinstance(item, NewsItem) for item in items)
        mock_news_repo.get_recent.assert_called_once_with(
            days=7, source="TechNews", limit=10
        )
    
    @pytest.mark.asyncio
    async def test_get_collection_summary(self):
        """Test getting collection summary statistics."""
        with patch('ai_news_agent.collectors.rss.settings') as mock_settings:
            mock_settings.rss_feeds = []
            mock_settings.max_age_days = 7
            collector = RSSCollectorWithStorage()
        
        with patch('ai_news_agent.collectors.rss_with_storage.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            mock_news_repo = AsyncMock()
            mock_collector_repo = AsyncMock()
            
            # Mock source counts
            mock_news_repo.count_by_source.return_value = [
                ("TechNews", 50),
                ("HealthTech", 30),
            ]
            
            # Mock collector stats
            mock_stats = MagicMock()
            mock_stats.success_count = 100
            mock_stats.failure_count = 5
            mock_stats.success_rate = 95.24
            mock_stats.average_items = 40.5
            mock_stats.average_response_time = 2.3
            mock_collector_repo.get_collector_stats.return_value = mock_stats
            
            # Mock recent runs
            mock_run = MagicMock()
            mock_run.started_at = datetime.now(UTC)
            mock_run.completed_at = datetime.now(UTC)
            mock_run.total_items = 80
            mock_run.new_items = 60
            mock_run.duplicate_items = 20
            mock_collector_repo.get_recent_runs.return_value = [mock_run]
            
            with patch('ai_news_agent.collectors.rss_with_storage.NewsItemRepository', return_value=mock_news_repo):
                with patch('ai_news_agent.collectors.rss_with_storage.CollectorRepository', return_value=mock_collector_repo):
                    summary = await collector.get_collection_summary(days=7)
        
        assert summary["period_days"] == 7
        assert summary["sources"]["TechNews"] == 50
        assert summary["sources"]["HealthTech"] == 30
        assert summary["total_items"] == 80
        assert summary["collector_stats"]["success_rate"] == 95.24
        assert len(summary["recent_runs"]) == 1
        assert summary["recent_runs"][0]["new_items"] == 60