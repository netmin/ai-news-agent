"""Tests for digest generation module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_news_agent.digest import DigestGenerator, MarkdownFormatter, NewsRanker
from ai_news_agent.models import NewsItem


@pytest.fixture
def sample_news_items():
    """Create sample news items for testing."""
    base_time = datetime.now(UTC)
    
    return [
        NewsItem(
            url="https://example.com/ai-breakthrough",
            title="Major AI Breakthrough Announced",
            content="Researchers have announced a significant breakthrough in artificial intelligence...",
            summary="New AI model achieves state-of-the-art performance",
            source="TechNews",
            published_at=base_time - timedelta(hours=2),
            collected_at=base_time,
            tags=["ai", "breaking", "technology"],
            metadata={"category": "AI"},
        ),
        NewsItem(
            url="https://example.com/security-alert",
            title="Critical Security Vulnerability Discovered",
            content="A critical security vulnerability has been found in popular software...",
            source="SecurityDaily",
            published_at=base_time - timedelta(hours=5),
            collected_at=base_time,
            tags=["security", "important"],
            metadata={},
        ),
        NewsItem(
            url="https://example.com/market-update",
            title="Tech Stocks Rally on Positive Earnings",
            content="Technology stocks showed strong gains following better than expected earnings...",
            source="FinanceNews",
            published_at=base_time - timedelta(hours=8),
            collected_at=base_time,
            tags=["finance", "technology"],
            metadata={},
        ),
        NewsItem(
            url="https://example.com/ai-research",
            title="New Research Paper on Machine Learning",
            content="Scientists publish groundbreaking research on neural network architectures...",
            source="TechNews",
            published_at=base_time - timedelta(hours=12),
            collected_at=base_time,
            tags=["ai", "research"],
            metadata={},
        ),
        NewsItem(
            url="https://example.com/tech-conference",
            title="Major Tech Conference Announces Speakers",
            content="The annual technology conference has revealed its speaker lineup...",
            source="TechNews",
            published_at=base_time - timedelta(hours=20),
            collected_at=base_time,
            tags=["technology", "conference"],
            metadata={},
        ),
    ]


class TestNewsRanker:
    """Test news ranking functionality."""
    
    def test_rank_items(self, sample_news_items):
        """Test ranking news items."""
        ranker = NewsRanker()
        
        ranked = ranker.rank_items(
            sample_news_items,
            max_items=3,
            max_per_source=2,
        )
        
        assert len(ranked) == 3
        assert all(isinstance(score, float) for _, score in ranked)
        assert all(0 <= score <= 1 for _, score in ranked)
        
        # Check that scores are sorted descending
        scores = [score for _, score in ranked]
        assert scores == sorted(scores, reverse=True)
        
        # Check source diversity
        sources = [item.source for item, _ in ranked]
        assert sources.count("TechNews") <= 2
    
    def test_rank_with_important_tags(self, sample_news_items):
        """Test that important tags boost ranking."""
        ranker = NewsRanker(relevance_weight=0.5)  # Increase relevance weight
        
        ranked = ranker.rank_items(sample_news_items)
        
        # Items with "breaking" or "important" tags should rank higher
        top_items = [item for item, _ in ranked[:2]]
        top_tags = [tag for item in top_items for tag in item.tags]
        
        assert "breaking" in top_tags or "important" in top_tags
    
    def test_group_by_category(self, sample_news_items):
        """Test grouping by category."""
        ranker = NewsRanker()
        # Get all items to ensure we have both AI articles
        ranked = ranker.rank_items(sample_news_items, max_items=5, max_per_source=3)
        
        grouped = ranker.group_by_category(ranked)
        
        # Test that grouping works correctly
        assert len(grouped) > 0  # At least one category
        
        # Test that items are properly categorized
        for category, items in grouped.items():
            assert len(items) > 0  # Each category has at least one item
            
        # Check that AI articles are properly categorized if AI category exists
        if "ai" in grouped:
            ai_titles = [item.title for item, _ in grouped["ai"]]
            assert any("AI" in title or "Machine Learning" in title for title in ai_titles)
    
    def test_get_top_topics(self, sample_news_items):
        """Test extracting top topics."""
        ranker = NewsRanker()
        
        top_topics = ranker.get_top_topics(sample_news_items, limit=3)
        
        assert len(top_topics) <= 3
        assert all(isinstance(count, int) for _, count in top_topics)
        assert top_topics[0][0] in ["technology", "ai"]  # Most common tags


class TestMarkdownFormatter:
    """Test Markdown formatting."""
    
    def test_format_daily_digest(self, sample_news_items):
        """Test formatting daily digest as Markdown."""
        formatter = MarkdownFormatter()
        ranker = NewsRanker()
        
        ranked = ranker.rank_items(sample_news_items, max_items=3)
        date = datetime.now(UTC)
        
        metadata = {
            "sources": ["TechNews", "SecurityDaily"],
            "categories": ["ai", "security"],
        }
        
        markdown = formatter.format_daily_digest(ranked, date, metadata)
        
        assert f"# Daily News Digest - {date.strftime('%Y-%m-%d')}" in markdown
        assert "**Total items:** 3" in markdown
        assert "**Sources:** TechNews, SecurityDaily" in markdown
        assert all(item.title in markdown for item, _ in ranked)
        assert "*Generated by AI News Agent*" in markdown
    
    def test_format_weekly_summary(self, sample_news_items):
        """Test formatting weekly summary as Markdown."""
        formatter = MarkdownFormatter()
        ranker = NewsRanker()
        
        ranked = ranker.rank_items(sample_news_items)
        week_start = datetime.now(UTC) - timedelta(days=7)
        week_end = datetime.now(UTC)
        top_topics = [("technology", 3), ("ai", 2)]
        
        metadata = {
            "total_collected": 50,
            "sources_count": 5,
            "ai_summary": "This week was dominated by AI news.",
        }
        
        markdown = formatter.format_weekly_summary(
            ranked, week_start, week_end, top_topics, metadata
        )
        
        assert "# Weekly News Summary" in markdown
        assert f"**Period:** {week_start.strftime('%Y-%m-%d')}" in markdown
        assert "## Top Topics This Week" in markdown
        assert "- **technology**: 3 articles" in markdown
        assert "## AI Summary" in markdown
        assert metadata["ai_summary"] in markdown


class TestDigestGenerator:
    """Test digest generator functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_daily_digest(self, sample_news_items):
        """Test generating daily digest."""
        generator = DigestGenerator()
        
        # Mock database
        with patch('ai_news_agent.digest.generator.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            # Mock repositories
            mock_digest_repo = AsyncMock()
            mock_digest_repo.get_daily_digest.return_value = None
            mock_digest_repo.create_daily_digest.return_value = MagicMock(
                id=1,
                date=datetime.now(UTC),
                content_markdown=None,
                content_html=None,
            )
            
            mock_news_repo = AsyncMock()
            # Convert NewsItems to mock DB items
            mock_db_items = []
            for item in sample_news_items:
                mock_db_item = MagicMock()
                for attr in ['id', 'url', 'title', 'content', 'summary', 
                            'source', 'published_at', 'collected_at', 'tags']:
                    setattr(mock_db_item, attr, getattr(item, attr))
                mock_db_item.extra_metadata = item.metadata
                mock_db_items.append(mock_db_item)
            
            mock_news_repo.get_recent.return_value = mock_db_items
            
            with patch('ai_news_agent.digest.generator.DigestRepository', return_value=mock_digest_repo):
                with patch('ai_news_agent.digest.generator.NewsItemRepository', return_value=mock_news_repo):
                    markdown, html = await generator.generate_daily_digest()
        
        assert markdown is not None
        assert html is not None
        assert "Daily News Digest" in markdown
        assert "<h1>Daily News Digest" in html
    
    @pytest.mark.asyncio
    async def test_generate_daily_digest_no_items(self):
        """Test generating digest with no items."""
        generator = DigestGenerator()
        
        with patch('ai_news_agent.digest.generator.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            mock_digest_repo = AsyncMock()
            mock_digest_repo.get_daily_digest.return_value = None
            
            mock_news_repo = AsyncMock()
            mock_news_repo.get_recent.return_value = []
            
            with patch('ai_news_agent.digest.generator.DigestRepository', return_value=mock_digest_repo):
                with patch('ai_news_agent.digest.generator.NewsItemRepository', return_value=mock_news_repo):
                    result = await generator.generate_daily_digest()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_weekly_summary(self, sample_news_items):
        """Test generating weekly summary."""
        generator = DigestGenerator()
        
        with patch('ai_news_agent.digest.generator.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            mock_digest_repo = AsyncMock()
            mock_digest_repo.get_weekly_summary.return_value = None
            mock_digest_repo.create_weekly_summary.return_value = MagicMock(
                id=1,
                week_start=datetime.now(UTC) - timedelta(days=7),
                week_end=datetime.now(UTC),
                content_markdown=None,
                content_html=None,
            )
            
            mock_news_repo = AsyncMock()
            # Convert NewsItems to mock DB items
            mock_db_items = []
            for item in sample_news_items:
                mock_db_item = MagicMock()
                for attr in ['id', 'url', 'title', 'content', 'summary', 
                            'source', 'published_at', 'collected_at', 'tags']:
                    setattr(mock_db_item, attr, getattr(item, attr))
                mock_db_item.extra_metadata = item.metadata
                mock_db_items.append(mock_db_item)
            
            mock_news_repo.get_recent.return_value = mock_db_items
            
            with patch('ai_news_agent.digest.generator.DigestRepository', return_value=mock_digest_repo):
                with patch('ai_news_agent.digest.generator.NewsItemRepository', return_value=mock_news_repo):
                    markdown, html = await generator.generate_weekly_summary()
        
        assert markdown is not None
        assert html is not None
        assert "Weekly News Summary" in markdown
        assert "Top Topics This Week" in markdown
        assert "<h1>Weekly News Summary</h1>" in html