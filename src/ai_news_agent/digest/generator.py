"""Main digest generator that orchestrates the digest creation process."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import select

from ..config import settings
from ..models import NewsItem
from ..storage import DigestRepository, NewsItemRepository, get_db_manager
from ..storage.models import DailyDigestDB, WeeklySummaryDB
from .formatters import HTMLFormatter, MarkdownFormatter
from .ranker import NewsRanker


class DigestGenerator:
    """Generates daily digests and weekly summaries from collected news items.

    Orchestrates the process of:
    1. Retrieving relevant news items from storage
    2. Ranking items by importance
    3. Formatting into readable digests
    4. Storing generated digests in database
    """

    def __init__(
        self,
        ranker: NewsRanker | None = None,
        markdown_formatter: MarkdownFormatter | None = None,
        html_formatter: HTMLFormatter | None = None,
    ):
        """Initialize digest generator.

        Args:
            ranker: News ranker instance
            markdown_formatter: Markdown formatter instance
            html_formatter: HTML formatter instance
        """
        self.ranker = ranker or NewsRanker()
        self.markdown_formatter = markdown_formatter or MarkdownFormatter()
        self.html_formatter = html_formatter or HTMLFormatter()

        # Load settings
        self.daily_item_limit = getattr(settings, "daily_digest_items", 20)
        self.weekly_item_limit = getattr(settings, "weekly_summary_items", 50)
        self.max_per_source_daily = getattr(settings, "max_per_source_daily", 3)
        self.max_per_source_weekly = getattr(settings, "max_per_source_weekly", 5)

    async def generate_daily_digest(
        self,
        date: datetime | None = None,
        force_regenerate: bool = False,
    ) -> tuple[str, str] | None:
        """Generate daily digest for a specific date.

        Args:
            date: Date to generate digest for (default: today)
            force_regenerate: Regenerate even if digest exists

        Returns:
            Tuple of (markdown, html) content or None if no items
        """
        date = date or datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            digest_repo = DigestRepository(session)
            news_repo = NewsItemRepository(session)

            # Check if digest already exists
            existing = await digest_repo.get_daily_digest(date)
            if existing and not force_regenerate:
                logger.info(f"Daily digest for {date.date()} already exists")
                return existing.content_markdown, existing.content_html

            # Get news items for the day
            start_time = date
            end_time = date + timedelta(days=1)

            items = await news_repo.get_recent(days=1)
            # Filter to exact date range
            items = [
                item for item in items if start_time <= item.published_at < end_time
            ]

            if not items:
                logger.info(f"No items found for {date.date()}")
                return None

            logger.info(f"Found {len(items)} items for {date.date()}")

            # Convert to NewsItem models
            news_items = []
            for db_item in items:
                news_item = NewsItem(
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
                news_items.append(news_item)

            # Rank items
            ranked_items = self.ranker.rank_items(
                news_items,
                max_items=self.daily_item_limit,
                max_per_source=self.max_per_source_daily,
                reference_time=date,
            )

            # Group by category
            grouped_items = self.ranker.group_by_category(ranked_items)

            # Prepare metadata
            sources = list({item.source for item, _ in ranked_items})
            categories = list(grouped_items.keys())

            metadata = {
                "sources": sources,
                "categories": categories,
                "grouped_items": grouped_items,
                "total_collected": len(items),
            }

            # Format content
            markdown_content = self.markdown_formatter.format_daily_digest(
                ranked_items, date, metadata
            )
            html_content = self.html_formatter.format_daily_digest(
                ranked_items, date, metadata
            )

            # Store in database
            if existing:
                existing.content_markdown = markdown_content
                existing.content_html = html_content
                existing.item_count = len(ranked_items)
                existing.extra_metadata = metadata
                logger.info(f"Updated daily digest for {date.date()}")
            else:
                digest = await digest_repo.create_daily_digest(
                    date,
                    [item for item, _ in ranked_items],  # Extract DB items
                )
                digest.content_markdown = markdown_content
                digest.content_html = html_content
                digest.extra_metadata = metadata
                logger.info(f"Created daily digest for {date.date()}")

            await session.commit()

            return markdown_content, html_content

    async def generate_weekly_summary(
        self,
        week_start: datetime | None = None,
        force_regenerate: bool = False,
        include_ai_summary: bool = False,
    ) -> tuple[str, str] | None:
        """Generate weekly summary.

        Args:
            week_start: Start of the week (default: last Monday)
            force_regenerate: Regenerate even if summary exists
            include_ai_summary: Generate AI summary (requires AI service)

        Returns:
            Tuple of (markdown, html) content or None if no items
        """
        if week_start is None:
            # Get last Monday
            today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday)

        week_end = week_start + timedelta(days=7)

        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            digest_repo = DigestRepository(session)
            news_repo = NewsItemRepository(session)

            # Check if summary already exists
            existing = await digest_repo.get_weekly_summary(week_start)
            if existing and not force_regenerate:
                logger.info(
                    f"Weekly summary for {week_start.date()} to "
                    f"{week_end.date()} already exists"
                )
                return existing.content_markdown, existing.content_html

            # Get all items for the week
            items = await news_repo.get_recent(days=7)
            # Filter to exact week range
            items = [
                item for item in items if week_start <= item.published_at < week_end
            ]

            if not items:
                logger.info(f"No items found for week {week_start.date()}")
                return None

            logger.info(f"Found {len(items)} items for week {week_start.date()}")

            # Convert to NewsItem models
            news_items = []
            for db_item in items:
                news_item = NewsItem(
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
                news_items.append(news_item)

            # Get top topics
            top_topics = self.ranker.get_top_topics(news_items, limit=10)

            # Rank all items
            all_ranked = self.ranker.rank_items(
                news_items,
                max_items=self.weekly_item_limit,
                max_per_source=self.max_per_source_weekly,
                reference_time=week_end,
            )

            # Group by day
            by_day = defaultdict(list)
            for item, score in all_ranked:
                day_key = item.published_at.strftime("%A, %B %d")
                by_day[day_key].append((item, score))

            # Sort days - keep original order from items (already sorted by date)
            # No need to re-sort since items are already in date order

            # Prepare metadata
            sources = {item.source for item in news_items}
            metadata = {
                "total_collected": len(items),
                "sources_count": len(sources),
                "by_day": by_day,
            }

            # Generate AI summary if requested
            if include_ai_summary:
                # This would require integration with AI service
                # For now, placeholder
                metadata["ai_summary"] = (
                    "This week's tech news was dominated by AI developments, "
                    "with several major announcements in machine learning. "
                    "Security remained a key concern with new vulnerabilities "
                    "discovered. "
                    "The open-source community saw increased activity "
                    "across various projects."
                )

            # Format content
            markdown_content = self.markdown_formatter.format_weekly_summary(
                all_ranked, week_start, week_end, top_topics, metadata
            )
            html_content = self.html_formatter.format_weekly_summary(
                all_ranked, week_start, week_end, top_topics, metadata
            )

            # Store in database
            if existing:
                existing.content_markdown = markdown_content
                existing.content_html = html_content
                existing.item_count = len(all_ranked)
                existing.top_topics = [topic for topic, _ in top_topics]
                existing.extra_metadata = metadata
                if include_ai_summary and "ai_summary" in metadata:
                    existing.ai_summary = metadata["ai_summary"]
                logger.info(f"Updated weekly summary for {week_start.date()}")
            else:
                summary = await digest_repo.create_weekly_summary(
                    week_start,
                    week_end,
                    [item for item, _ in all_ranked],
                    [topic for topic, _ in top_topics],
                )
                summary.content_markdown = markdown_content
                summary.content_html = html_content
                summary.extra_metadata = metadata
                if include_ai_summary and "ai_summary" in metadata:
                    summary.ai_summary = metadata["ai_summary"]
                logger.info(f"Created weekly summary for {week_start.date()}")

            await session.commit()

            return markdown_content, html_content

    async def get_unsent_digests(self) -> tuple[list, list]:
        """Get all unsent digests and summaries.

        Returns:
            Tuple of (daily_digests, weekly_summaries)
        """
        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            digest_repo = DigestRepository(session)
            return await digest_repo.get_unsent_digests()

    async def mark_as_sent(self, digest_id: int, digest_type: str = "daily") -> None:
        """Mark a digest as sent.

        Args:
            digest_id: Digest ID
            digest_type: Type of digest ("daily" or "weekly")
        """
        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            digest_repo = DigestRepository(session)

            if digest_type == "daily":
                result = await session.execute(
                    select(DailyDigestDB).where(DailyDigestDB.id == digest_id)
                )
                result = result.scalar_one_or_none()
            else:
                result = await session.execute(
                    select(WeeklySummaryDB).where(WeeklySummaryDB.id == digest_id)
                )
                result = result.scalar_one_or_none()

            if result:
                await digest_repo.mark_digest_sent(result)
                await session.commit()
                logger.info(f"Marked {digest_type} digest {digest_id} as sent")
