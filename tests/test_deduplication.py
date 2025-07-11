"""Tests for enhanced deduplication service."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from ai_news_agent.deduplication import DeduplicationService, EmbeddingService
from ai_news_agent.deduplication.service import DuplicateMatch
from ai_news_agent.models import NewsItem


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory."""
    cache_dir = tmp_path / "embeddings_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def embedding_service(temp_cache_dir):
    """Create embedding service with temporary cache."""
    return EmbeddingService(
        model_name="all-MiniLM-L6-v2",
        cache_dir=temp_cache_dir
    )


@pytest.fixture
def dedup_service(embedding_service):
    """Create deduplication service."""
    return DeduplicationService(
        embedding_service=embedding_service,
        similarity_threshold=0.85,
        lookback_days=30
    )


@pytest.fixture
def sample_news_item():
    """Create sample news item."""
    return NewsItem(
        url="https://example.com/article1",
        title="Breaking: Major Tech Announcement",
        content="A major technology company announced groundbreaking innovations today...",
        source="TechNews",
        published_at=datetime.now(UTC),
        collected_at=datetime.now(UTC),
        tags=["tech", "breaking"],
        metadata={"category": "technology"}
    )


class TestEmbeddingService:
    """Test embedding service functionality."""
    
    def test_encode_text(self, embedding_service):
        """Test encoding single text."""
        text = "This is a test article about technology"
        embedding = embedding_service.encode(text)
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (embedding_service.embedding_dim,)
        assert not np.all(embedding == 0)  # Should not be zero vector
    
    def test_encode_batch(self, embedding_service):
        """Test batch encoding."""
        texts = [
            "First article about AI",
            "Second article about machine learning",
            "Third article about data science"
        ]
        embeddings = embedding_service.encode_batch(texts)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, embedding_service.embedding_dim)
        assert not np.all(embeddings == 0)
    
    def test_cosine_similarity(self, embedding_service):
        """Test cosine similarity calculation."""
        # Similar texts should have high similarity
        text1 = "Artificial intelligence breakthrough announced"
        text2 = "AI technology makes major advancement"
        
        emb1 = embedding_service.encode(text1)
        emb2 = embedding_service.encode(text2)
        
        similarity = embedding_service.cosine_similarity(emb1, emb2)
        assert 0 <= similarity <= 1
        assert similarity > 0.5  # Should be somewhat similar
        
        # Different texts should have lower similarity
        text3 = "Weather forecast predicts rain tomorrow"
        emb3 = embedding_service.encode(text3)
        
        similarity2 = embedding_service.cosine_similarity(emb1, emb3)
        assert similarity2 < similarity  # Less similar than AI texts
    
    def test_caching(self, embedding_service, temp_cache_dir):
        """Test embedding caching."""
        text = "This text should be cached"
        
        # First encoding should create cache
        embedding1 = embedding_service.encode(text)
        
        # Check cache file exists
        cache_files = list(temp_cache_dir.rglob("*.npy"))
        assert len(cache_files) > 0
        
        # Second encoding should use cache
        with patch.object(embedding_service.model, 'encode') as mock_encode:
            embedding2 = embedding_service.encode(text)
            mock_encode.assert_not_called()  # Should not call model
        
        assert np.array_equal(embedding1, embedding2)
    
    def test_find_most_similar(self, embedding_service):
        """Test finding most similar embeddings."""
        query = "Latest AI research paper published"
        candidates = [
            "New machine learning algorithm discovered",
            "Weather update for tomorrow",
            "Recent advances in artificial intelligence",
            "Stock market closes higher today"
        ]
        
        query_emb = embedding_service.encode(query)
        candidate_embs = embedding_service.encode_batch(candidates)
        
        similar = embedding_service.find_most_similar(
            query_emb, candidate_embs, threshold=0.6, top_k=2
        )
        
        assert len(similar) <= 2
        assert all(score >= 0.6 for _, score in similar)
        # AI-related candidates should rank higher
        top_indices = [idx for idx, _ in similar]
        assert 0 in top_indices or 2 in top_indices


class TestDeduplicationService:
    """Test deduplication service functionality."""
    
    @pytest.mark.asyncio
    async def test_exact_url_duplicate(self, dedup_service, sample_news_item):
        """Test detection of exact URL duplicates."""
        # Mock the database checks
        with patch('ai_news_agent.deduplication.service.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            # Mock repository responses
            mock_news_repo = AsyncMock()
            mock_news_repo.get_by_url.return_value = MagicMock(
                id="existing_id_123",
                url=sample_news_item.url
            )
            
            with patch('ai_news_agent.deduplication.service.NewsItemRepository', return_value=mock_news_repo):
                result = await dedup_service.check_duplicate(sample_news_item)
        
        assert result.is_duplicate is True
        assert result.original_id == "existing_id_123"
        assert result.similarity_score == 1.0
        assert result.match_type == "exact_url"
    
    @pytest.mark.asyncio
    async def test_semantic_similarity_duplicate(self, dedup_service, sample_news_item):
        """Test detection of semantically similar content."""
        # Create a similar item with different URL but similar content
        similar_item = NewsItem(
            url="https://different-site.com/news",
            title="Breaking News: Big Technology Announcement",  # Similar title
            content="A major tech company revealed groundbreaking innovations...",  # Similar content
            source="TechDaily",
            published_at=sample_news_item.published_at,
            collected_at=datetime.now(UTC),
            tags=["technology"],
            metadata={}
        )
        
        # Set up the deduplication service with cached items
        dedup_service._cache_loaded = True
        dedup_service._items_cache = [(
            MagicMock(
                id="cached_item_123",
                title=sample_news_item.title,
                content=sample_news_item.content,
                url=sample_news_item.url,
                published_at=sample_news_item.published_at
            ),
            dedup_service.embedding_service.encode(
                dedup_service.embedding_service.combine_text_for_similarity(
                    sample_news_item.title,
                    sample_news_item.content,
                    str(sample_news_item.url)
                )
            )
        )]
        
        # Mock database checks to return no exact matches
        with patch('ai_news_agent.deduplication.service.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            mock_news_repo = AsyncMock()
            mock_news_repo.get_by_url.return_value = None
            
            mock_dedup_repo = AsyncMock()
            mock_dedup_repo.find_similar.return_value = None
            
            with patch('ai_news_agent.deduplication.service.NewsItemRepository', return_value=mock_news_repo):
                with patch('ai_news_agent.deduplication.service.DeduplicationRepository', return_value=mock_dedup_repo):
                    result = await dedup_service.check_duplicate(similar_item)
        
        # Should detect as duplicate due to semantic similarity
        assert result.is_duplicate is True
        assert result.original_id == "cached_item_123"
        assert result.similarity_score > 0.8  # High similarity
        assert result.match_type == "similar_content"
    
    @pytest.mark.asyncio
    async def test_no_duplicate(self, dedup_service, sample_news_item):
        """Test when item is not a duplicate."""
        # Set up empty cache
        dedup_service._cache_loaded = True
        dedup_service._items_cache = []
        
        # Mock database checks to return no matches
        with patch('ai_news_agent.deduplication.service.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            mock_news_repo = AsyncMock()
            mock_news_repo.get_by_url.return_value = None
            
            mock_dedup_repo = AsyncMock()
            mock_dedup_repo.find_similar.return_value = None
            
            with patch('ai_news_agent.deduplication.service.NewsItemRepository', return_value=mock_news_repo):
                with patch('ai_news_agent.deduplication.service.DeduplicationRepository', return_value=mock_dedup_repo):
                    result = await dedup_service.check_duplicate(sample_news_item)
        
        assert result.is_duplicate is False
        assert result.original_id is None
        assert result.similarity_score == 0.0
        assert result.match_type == "none"
    
    @pytest.mark.asyncio
    async def test_time_based_filtering(self, dedup_service, sample_news_item):
        """Test that old similar content is not considered duplicate."""
        # Create item with similar content but old publish date
        old_date = datetime.now(UTC) - timedelta(days=10)
        
        dedup_service._cache_loaded = True
        dedup_service._items_cache = [(
            MagicMock(
                id="old_item_123",
                title=sample_news_item.title,
                content=sample_news_item.content,
                url="https://old-news.com/article",
                published_at=old_date  # Published 10 days ago
            ),
            dedup_service.embedding_service.encode(
                dedup_service.embedding_service.combine_text_for_similarity(
                    sample_news_item.title,
                    sample_news_item.content,
                    "https://old-news.com/article"
                )
            )
        )]
        
        # Mock database checks
        with patch('ai_news_agent.deduplication.service.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            mock_news_repo = AsyncMock()
            mock_news_repo.get_by_url.return_value = None
            
            mock_dedup_repo = AsyncMock()
            mock_dedup_repo.find_similar.return_value = None
            
            with patch('ai_news_agent.deduplication.service.NewsItemRepository', return_value=mock_news_repo):
                with patch('ai_news_agent.deduplication.service.DeduplicationRepository', return_value=mock_dedup_repo):
                    result = await dedup_service.check_duplicate(sample_news_item)
        
        # Should not be duplicate due to time difference
        assert result.is_duplicate is False
        assert result.match_type == "none"
    
    @pytest.mark.asyncio
    async def test_batch_check(self, dedup_service):
        """Test batch duplicate checking."""
        items = [
            NewsItem(
                url=f"https://example.com/article{i}",
                title=f"Article {i}",
                content=f"Content for article {i}",
                source="TestSource",
                published_at=datetime.now(UTC),
                collected_at=datetime.now(UTC),
                tags=[],
                metadata={}
            )
            for i in range(3)
        ]
        
        # Set up empty cache
        dedup_service._cache_loaded = True
        dedup_service._items_cache = []
        
        # Mock the exact match checks
        with patch.object(dedup_service, '_check_exact_matches') as mock_check:
            mock_check.return_value = DuplicateMatch(
                is_duplicate=False,
                original_id=None,
                similarity_score=0.0,
                match_type="none"
            )
            
            results = await dedup_service.check_batch(items)
        
        assert len(results) == 3
        assert all(not result.is_duplicate for result in results)
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, dedup_service, temp_cache_dir):
        """Test cleanup of old deduplication data."""
        # Create some old cache files
        old_file = temp_cache_dir / "00" / "old_file.npy"
        old_file.parent.mkdir(exist_ok=True)
        np.save(old_file, np.array([1, 2, 3]))
        
        # Mock database cleanup
        with patch('ai_news_agent.deduplication.service.get_db_manager') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.get_session.return_value.__aenter__.return_value = mock_session
            
            mock_dedup_repo = AsyncMock()
            mock_dedup_repo.cleanup_old_entries.return_value = 5
            
            with patch('ai_news_agent.deduplication.service.DeduplicationRepository', return_value=mock_dedup_repo):
                # Make file appear old
                import os
                old_time = (datetime.now(UTC) - timedelta(days=40)).timestamp()
                os.utime(old_file, (old_time, old_time))
                
                stats = await dedup_service.cleanup_old_data(days=30)
        
        assert stats["database_entries_removed"] == 5
        assert not old_file.exists()  # Old file should be removed