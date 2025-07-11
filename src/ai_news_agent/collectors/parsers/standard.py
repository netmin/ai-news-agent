"""Standard RSS/Atom feed parser for most RSS feeds"""

from datetime import UTC, datetime
from typing import Any

import feedparser
from loguru import logger

from ...models import NewsItem
from .base import BaseParser


class StandardParser(BaseParser):
    """Parser for standard RSS 2.0 and Atom feeds

    Handles most common RSS feed formats including:
    - TechCrunch
    - The Verge
    - OpenAI Blog
    - Anthropic Blog
    """

    async def parse(self, content: str) -> list[NewsItem]:
        """Parse standard RSS/Atom feed content

        Args:
            content: Raw RSS/XML content as string

        Returns:
            List of validated NewsItem objects
        """
        items: list[NewsItem] = []

        try:
            # Parse RSS feed
            feed = feedparser.parse(content)

            if feed.bozo:
                logger.warning(
                    f"Feed parsing warning for {self.source_name}: "
                    f"{feed.bozo_exception}"
                )

            # Process each entry
            for entry in feed.entries:
                try:
                    item = self._parse_entry(entry)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.error(
                        f"Error parsing entry in {self.source_name}: {e}",
                        extra={"entry_title": entry.get("title", "Unknown")},
                    )
                    continue

            logger.info(f"Parsed {len(items)} items from {self.source_name}")

        except Exception as e:
            logger.error(f"Critical error parsing {self.source_name}: {e}")

        return items

    def _parse_entry(self, entry: dict[str, Any]) -> NewsItem | None:
        """Parse a single feed entry into NewsItem

        Args:
            entry: Feed entry from feedparser

        Returns:
            NewsItem object or None if required fields missing
        """
        # Extract required fields
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()

        if not title or not link:
            logger.debug(f"Skipping entry without title or link in {self.source_name}")
            return None

        # Extract content/summary
        content = ""
        if hasattr(entry, "content") and entry.content:
            # Some feeds have full content
            content = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            content = entry.summary
        elif hasattr(entry, "description"):
            content = entry.description

        # Clean HTML from content
        content = self._clean_html(content)

        # Extract summary (first 200 chars of content if not provided)
        summary = entry.get("summary", "")
        if not summary and content:
            summary = content[:200] + "..." if len(content) > 200 else content
        summary = self._clean_html(summary)

        # Parse publication date
        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published_at = datetime(*entry.updated_parsed[:6])
        elif hasattr(entry, "published"):
            published_at = self._parse_date(entry.published)
        elif hasattr(entry, "updated"):
            published_at = self._parse_date(entry.updated)

        if not published_at:
            # Use current time if no date found
            published_at = datetime.now(UTC)
            logger.debug(f"No publication date found for '{title}', using current time")

        # Extract tags from categories
        tags = []
        if hasattr(entry, "tags"):
            tags = [tag.get("term", "") for tag in entry.tags if tag.get("term")]

        # Extract author for metadata
        metadata = {}
        if hasattr(entry, "author"):
            metadata["author"] = entry.author
        elif hasattr(entry, "authors"):
            metadata["authors"] = ", ".join(
                author.get("name", "") for author in entry.authors
            )

        # Add GUID if available
        if hasattr(entry, "id"):
            metadata["guid"] = entry.id

        # Create NewsItem
        try:
            return NewsItem(
                url=link,
                title=title,
                content=content,
                summary=summary,
                source=self.source_name,
                published_at=published_at,
                tags=tags,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(
                f"Failed to create NewsItem: {e}", extra={"title": title, "url": link}
            )
            return None
