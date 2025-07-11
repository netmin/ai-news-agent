"""RSS feed collector with storage integration."""

from datetime import UTC, datetime, timedelta

from loguru import logger

from ..config import settings
from ..deduplication import DeduplicationService
from ..models import NewsItem
from ..storage import (
    CollectorRepository,
    DeduplicationRepository,
    NewsItemRepository,
    get_db_manager,
)
from .rss import RSSCollector


class RSSCollectorWithStorage(RSSCollector):
    """RSS Collector with database storage integration.

    Extends the base RSS collector to:
    - Store collected items in the database
    - Track collector runs with statistics
    - Perform database-based deduplication
    - Handle duplicate marking
    - Use semantic similarity for enhanced deduplication
    """
    
    def __init__(self, feeds: list[dict] | None = None):
        """Initialize collector with optional feeds list."""
        super().__init__(feeds)
        self.dedup_service = DeduplicationService()

    async def collect_and_store(self) -> tuple[list[NewsItem], dict]:
        """Collect news items and store them in the database.

        Returns:
            Tuple of (new_items, statistics)
            - new_items: List of newly collected non-duplicate items
            - statistics: Dict with collection statistics
        """
        db_manager = get_db_manager()

        # Collect items using parent class
        collected_items = await self.collect()

        if not collected_items:
            logger.info("No items collected from RSS feeds")
            return [], {"total": 0, "new": 0, "duplicates": 0}

        # Store items in database
        async with db_manager.get_session() as session:
            news_repo = NewsItemRepository(session)
            collector_repo = CollectorRepository(session)
            dedup_repo = DeduplicationRepository(session)

            # Create collector run
            run = await collector_repo.create_run("rss")

            new_items = []
            duplicate_count = 0
            failed_sources = []

            # Batch check for duplicates using enhanced deduplication
            duplicate_results = await self.dedup_service.check_batch(collected_items)
            
            # Process each item based on duplicate check results
            for item, dup_result in zip(collected_items, duplicate_results):
                try:
                    if dup_result.is_duplicate:
                        duplicate_count += 1
                        logger.debug(
                            f"Duplicate found for '{item.title}' "
                            f"(type: {dup_result.match_type}, "
                            f"score: {dup_result.similarity_score:.3f})"
                        )
                        continue

                    # Create new item
                    db_item = await news_repo.create(item)

                    # Add to deduplication cache
                    await dedup_repo.add_to_cache(db_item)
                    await self.dedup_service.add_to_cache(item)

                    new_items.append(item)
                    logger.info(f"Stored new item: {item.title}")

                except Exception as e:
                    logger.error(f"Failed to process item {item.url}: {e}")
                    if item.source not in failed_sources:
                        failed_sources.append(item.source)

            # Link items to collector run
            if new_items:
                item_ids = [item.id for item in new_items]
                await collector_repo.link_items_to_run(run.id, item_ids)

            # Complete the run with statistics
            stats = await self.get_stats()
            collector_stats = {
                stat.source: {
                    "success_rate": stat.success_rate,
                    "average_response_time": stat.average_response_time,
                    "last_success": (
                        stat.last_success.isoformat() if stat.last_success else None
                    ),
                }
                for stat in stats
            }

            await collector_repo.complete_run(
                run.id,
                total_items=len(collected_items),
                new_items=len(new_items),
                duplicate_items=duplicate_count,
                failed_sources=failed_sources,
                statistics=collector_stats,
            )

            # Commit all changes
            await session.commit()

            # Log summary
            logger.info(
                f"Collection complete: {len(collected_items)} total, "
                f"{len(new_items)} new, {duplicate_count} duplicates"
            )

            return new_items, {
                "total": len(collected_items),
                "new": len(new_items),
                "duplicates": duplicate_count,
                "failed_sources": failed_sources,
                "run_id": run.id,
            }

    async def cleanup_old_duplicates(self, days: int = 30) -> dict[str, int]:
        """Clean up old entries from deduplication cache.

        Args:
            days: Remove entries older than this many days

        Returns:
            Dict with cleanup statistics
        """
        # Clean up using enhanced deduplication service
        cleanup_stats = await self.dedup_service.cleanup_old_data(days)
        
        # Also clear memory cache if needed
        self.dedup_service.clear_memory_cache()
        
        logger.info(
            f"Cleaned up deduplication data: "
            f"{cleanup_stats['database_entries_removed']} DB entries, "
            f"{cleanup_stats['cache_files_removed']} cache files"
        )
        
        return cleanup_stats

    async def get_recent_items(
        self, days: int = 7, source: str | None = None, limit: int | None = None
    ) -> list[NewsItem]:
        """Get recently collected items from database.

        Args:
            days: Number of days to look back
            source: Filter by source (optional)
            limit: Maximum number of items to return

        Returns:
            List of recent NewsItem objects
        """
        db_manager = get_db_manager()

        async with db_manager.get_session() as session:
            news_repo = NewsItemRepository(session)
            db_items = await news_repo.get_recent(days=days, source=source, limit=limit)

            # Convert DB items to NewsItem models
            items = []
            for db_item in db_items:
                item = NewsItem(
                    id=db_item.id,
                    url=db_item.url,
                    title=db_item.title,
                    content=db_item.content,
                    summary=db_item.summary,
                    source=db_item.source,
                    published_at=db_item.published_at,
                    collected_at=db_item.collected_at,
                    tags=db_item.tags,
                    metadata=db_item.extra_metadata,
                )
                items.append(item)

            return items

    async def get_collection_summary(self, days: int = 7) -> dict:
        """Get summary of collection activity.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with collection summary statistics
        """
        db_manager = get_db_manager()

        async with db_manager.get_session() as session:
            news_repo = NewsItemRepository(session)
            collector_repo = CollectorRepository(session)

            # Get counts by source
            start_date = datetime.now(UTC) - timedelta(days=days)
            source_counts = await news_repo.count_by_source(start_date)

            # Get collector stats
            stats = await collector_repo.get_collector_stats("rss", days=days)

            # Get recent runs
            recent_runs = await collector_repo.get_recent_runs("rss", limit=10)

            return {
                "period_days": days,
                "sources": dict(source_counts),
                "total_items": sum(count for _, count in source_counts),
                "collector_stats": {
                    "success_count": stats.success_count,
                    "failure_count": stats.failure_count,
                    "success_rate": stats.success_rate,
                    "average_items": stats.average_items,
                    "average_response_time": stats.average_response_time,
                },
                "recent_runs": [
                    {
                        "started_at": run.started_at.isoformat(),
                        "completed_at": (
                            run.completed_at.isoformat() if run.completed_at else None
                        ),
                        "total_items": run.total_items,
                        "new_items": run.new_items,
                        "duplicate_items": run.duplicate_items,
                    }
                    for run in recent_runs
                ],
            }
