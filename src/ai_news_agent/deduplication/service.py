"""Enhanced deduplication service with semantic similarity."""

from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import numpy as np
from loguru import logger

from ..config import settings
from ..models import NewsItem
from ..storage import DeduplicationRepository, NewsItemRepository, get_db_manager
from ..storage.models import NewsItemDB
from .embeddings import EmbeddingService


class DuplicateMatch(NamedTuple):
    """Result of duplicate detection."""

    is_duplicate: bool
    original_id: str | None
    similarity_score: float
    match_type: str  # 'exact_url', 'exact_title', 'similar_content'


class DeduplicationService:
    """Enhanced deduplication service using embeddings for semantic similarity.

    Combines multiple strategies:
    1. Exact URL matching (fastest)
    2. Exact title matching
    3. Semantic similarity using embeddings
    4. Time-based filtering to avoid comparing with very old items
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        similarity_threshold: float | None = None,
        lookback_days: int | None = None,
    ):
        """Initialize deduplication service.

        Args:
            embedding_service: Service for generating embeddings
            similarity_threshold: Threshold for considering items similar
            lookback_days: How many days back to check for duplicates
        """
        self.embedding_service = embedding_service or EmbeddingService()
        self.similarity_threshold = similarity_threshold or getattr(
            settings, "content_similarity_threshold", 0.85
        )
        self.lookback_days = lookback_days or getattr(
            settings, "deduplication_lookback_days", 30
        )

        # Cache for current session
        self._embedding_cache: dict[str, np.ndarray] = {}
        self._items_cache: list[tuple[NewsItemDB, np.ndarray]] = []
        self._cache_loaded = False

    async def load_recent_items_cache(self) -> None:
        """Load recent items and their embeddings into memory cache."""
        if self._cache_loaded:
            return

        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            news_repo = NewsItemRepository(session)

            # Get recent items
            recent_items = await news_repo.get_recent(
                days=self.lookback_days,
                limit=1000,  # Reasonable limit for memory
            )

            if not recent_items:
                self._cache_loaded = True
                return

            # Generate embeddings for all items
            logger.info(f"Loading embeddings for {len(recent_items)} recent items")

            texts = []
            for item in recent_items:
                combined_text = self.embedding_service.combine_text_for_similarity(
                    item.title, item.content, item.url
                )
                texts.append(combined_text)

            # Batch encode
            embeddings = self.embedding_service.encode_batch(texts)

            # Store in cache
            self._items_cache = list(zip(recent_items, embeddings, strict=False))
            for item, embedding in self._items_cache:
                self._embedding_cache[item.id] = embedding

            self._cache_loaded = True
            logger.info(
                f"Loaded {len(self._items_cache)} items into deduplication cache"
            )

    async def check_duplicate(self, news_item: NewsItem) -> DuplicateMatch:
        """Check if a news item is a duplicate.

        Args:
            news_item: News item to check

        Returns:
            DuplicateMatch with detection results
        """
        # Ensure cache is loaded
        await self.load_recent_items_cache()

        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            news_repo = NewsItemRepository(session)
            dedup_repo = DeduplicationRepository(session)

            # 1. Check exact URL match (fastest)
            existing = await news_repo.get_by_url(str(news_item.url))
            if existing:
                return DuplicateMatch(
                    is_duplicate=True,
                    original_id=existing.id,
                    similarity_score=1.0,
                    match_type="exact_url",
                )

            # 2. Check deduplication cache for exact matches
            similar_cached = await dedup_repo.find_similar(
                str(news_item.url),
                news_item.title,
                news_item.content,
                threshold=0.99,  # Very high threshold for exact matches
            )
            if similar_cached:
                return DuplicateMatch(
                    is_duplicate=True,
                    original_id=similar_cached.news_item_id,
                    similarity_score=1.0,
                    match_type="exact_title",
                )

            # 3. Semantic similarity check
            if self._items_cache:
                # Generate embedding for new item
                combined_text = self.embedding_service.combine_text_for_similarity(
                    news_item.title, news_item.content, str(news_item.url)
                )
                item_embedding = self.embedding_service.encode(combined_text)

                # Compare with cached items
                candidate_embeddings = np.array([emb for _, emb in self._items_cache])
                similar_items = self.embedding_service.find_most_similar(
                    item_embedding,
                    candidate_embeddings,
                    threshold=self.similarity_threshold,
                    top_k=5,  # Check top 5 matches
                )

                if similar_items:
                    # Get the most similar item
                    best_idx, best_score = similar_items[0]
                    best_item, _ = self._items_cache[best_idx]

                    # Additional validation: check if published dates are close
                    time_diff = abs(
                        (
                            news_item.published_at - best_item.published_at
                        ).total_seconds()
                    )
                    # If published more than 7 days apart, probably not duplicate
                    if time_diff > 7 * 24 * 3600:
                        logger.debug(
                            f"Similar content found but published "
                            f"{time_diff / 3600:.1f} hours apart, "
                            f"not considering as duplicate"
                        )
                    else:
                        logger.info(
                            f"Duplicate found via semantic similarity: "
                            f"'{news_item.title}' similar to '{best_item.title}' "
                            f"(score: {best_score:.3f})"
                        )
                        return DuplicateMatch(
                            is_duplicate=True,
                            original_id=best_item.id,
                            similarity_score=best_score,
                            match_type="similar_content",
                        )

        return DuplicateMatch(
            is_duplicate=False,
            original_id=None,
            similarity_score=0.0,
            match_type="none",
        )

    async def add_to_cache(self, news_item: NewsItem) -> None:
        """Add a news item to the deduplication cache.

        Args:
            news_item: News item to add
        """
        # Generate embedding
        combined_text = self.embedding_service.combine_text_for_similarity(
            news_item.title, news_item.content, str(news_item.url)
        )
        embedding = self.embedding_service.encode(combined_text)

        # Add to memory cache
        self._embedding_cache[news_item.id] = embedding

        # Note: The database cache update is handled by the storage layer

    async def check_batch(self, news_items: list[NewsItem]) -> list[DuplicateMatch]:
        """Check multiple news items for duplicates efficiently.

        Args:
            news_items: List of news items to check

        Returns:
            List of DuplicateMatch results
        """
        # Ensure cache is loaded
        await self.load_recent_items_cache()

        results = []

        # Generate embeddings for all new items
        texts = []
        for item in news_items:
            combined_text = self.embedding_service.combine_text_for_similarity(
                item.title, item.content, str(item.url)
            )
            texts.append(combined_text)

        new_embeddings = self.embedding_service.encode_batch(texts)

        # Check each item
        for item, embedding in zip(news_items, new_embeddings, strict=False):
            # First try fast checks (URL, exact title)
            result = await self._check_exact_matches(item)
            if result.is_duplicate:
                results.append(result)
                continue

            # Semantic similarity check
            if self._items_cache:
                candidate_embeddings = np.array([emb for _, emb in self._items_cache])
                similar_items = self.embedding_service.find_most_similar(
                    embedding,
                    candidate_embeddings,
                    threshold=self.similarity_threshold,
                    top_k=1,
                )

                if similar_items:
                    best_idx, best_score = similar_items[0]
                    best_item, _ = self._items_cache[best_idx]

                    # Time-based validation
                    time_diff = abs(
                        (item.published_at - best_item.published_at).total_seconds()
                    )
                    if time_diff <= 7 * 24 * 3600:  # Within 7 days
                        results.append(
                            DuplicateMatch(
                                is_duplicate=True,
                                original_id=best_item.id,
                                similarity_score=best_score,
                                match_type="similar_content",
                            )
                        )
                        continue

            results.append(
                DuplicateMatch(
                    is_duplicate=False,
                    original_id=None,
                    similarity_score=0.0,
                    match_type="none",
                )
            )

        return results

    async def _check_exact_matches(self, news_item: NewsItem) -> DuplicateMatch:
        """Check for exact URL or title matches.

        Args:
            news_item: News item to check

        Returns:
            DuplicateMatch result
        """
        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            news_repo = NewsItemRepository(session)

            # Check exact URL
            existing = await news_repo.get_by_url(str(news_item.url))
            if existing:
                return DuplicateMatch(
                    is_duplicate=True,
                    original_id=existing.id,
                    similarity_score=1.0,
                    match_type="exact_url",
                )

        return DuplicateMatch(
            is_duplicate=False,
            original_id=None,
            similarity_score=0.0,
            match_type="none",
        )

    def clear_memory_cache(self) -> None:
        """Clear the in-memory cache."""
        self._embedding_cache.clear()
        self._items_cache.clear()
        self._cache_loaded = False
        logger.info("Cleared deduplication memory cache")

    async def cleanup_old_data(self, days: int | None = None) -> dict[str, int]:
        """Clean up old deduplication data.

        Args:
            days: Days to keep (default: 2x lookback_days)

        Returns:
            Dict with cleanup statistics
        """
        days = days or (self.lookback_days * 2)

        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            dedup_repo = DeduplicationRepository(session)

            # Clean database cache
            db_removed = await dedup_repo.cleanup_old_entries(days)
            await session.commit()

        # Clean embedding cache files older than threshold
        cache_removed = 0
        cutoff_time = datetime.now(UTC) - timedelta(days=days)

        for cache_file in self.embedding_service.cache_dir.rglob("*.npy"):
            try:
                # Check file modification time
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=UTC)
                if mtime < cutoff_time:
                    cache_file.unlink()
                    cache_removed += 1
            except Exception as e:
                logger.warning(f"Failed to check/remove cache file {cache_file}: {e}")

        logger.info(
            f"Cleanup complete: {db_removed} DB entries, "
            f"{cache_removed} embedding cache files removed"
        )

        return {
            "database_entries_removed": db_removed,
            "cache_files_removed": cache_removed,
        }
