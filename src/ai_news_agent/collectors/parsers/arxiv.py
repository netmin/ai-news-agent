"""ArXiv-specific RSS feed parser"""

from datetime import UTC, datetime
from typing import Any

import feedparser
from loguru import logger

from ...models import NewsItem
from .base import BaseParser


class ArxivParser(BaseParser):
    """Parser specifically for ArXiv RSS feeds

    ArXiv uses a different RSS format with Dublin Core elements:
    - Uses <dc:creator> instead of <author>
    - Uses <dc:date> for publication date
    - Different namespace handling
    """

    async def parse(self, content: str) -> list[NewsItem]:
        """Parse ArXiv RSS feed content

        Args:
            content: Raw RSS/XML content as string

        Returns:
            List of validated NewsItem objects
        """
        items: list[NewsItem] = []

        try:
            # Parse RSS feed with namespace support
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
                        f"Error parsing ArXiv entry: {e}",
                        extra={"entry_title": entry.get("title", "Unknown")},
                    )
                    continue

            logger.info(f"Parsed {len(items)} papers from {self.source_name}")

        except Exception as e:
            logger.error(f"Critical error parsing {self.source_name}: {e}")

        return items

    def _parse_entry(self, entry: dict[str, Any]) -> NewsItem | None:
        """Parse a single ArXiv feed entry into NewsItem

        Args:
            entry: Feed entry from feedparser

        Returns:
            NewsItem object or None if required fields missing
        """
        # Extract required fields
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()

        if not title or not link:
            logger.debug("Skipping ArXiv entry without title or link")
            return None

        # Extract abstract/description
        content = entry.get("description", "").strip()
        content = self._clean_html(content)

        # For ArXiv, summary is usually the same as description
        summary = content[:200] + "..." if len(content) > 200 else content

        # Parse publication date from dc:date
        published_at = None
        if hasattr(entry, "dc_date"):
            published_at = self._parse_date(entry.dc_date)
        elif hasattr(entry, "published"):
            published_at = self._parse_date(entry.published)
        elif hasattr(entry, "updated"):
            published_at = self._parse_date(entry.updated)

        if not published_at:
            published_at = datetime.now(UTC)
            logger.debug(f"No publication date found for ArXiv paper '{title}'")

        # Extract authors from dc:creator
        metadata = {}
        authors = []

        if hasattr(entry, "dc_creator"):
            # dc:creator is a comma-separated list of authors
            authors = [
                author.strip()
                for author in entry.dc_creator.split(",")
                if author.strip()
            ]
            metadata["authors"] = ", ".join(authors)
        elif hasattr(entry, "authors"):
            # Fallback to standard authors field
            authors = [
                author.get("name", "") for author in entry.authors if author.get("name")
            ]
            metadata["authors"] = ", ".join(authors)

        # Extract ArXiv ID from link
        if "arxiv.org/abs/" in link:
            arxiv_id = link.split("/abs/")[-1]
            metadata["arxiv_id"] = arxiv_id

            # Extract categories from ArXiv ID if present
            # ArXiv IDs often have format: YYMM.NNNNN or category/YYMMNNN
            if "/" in arxiv_id:
                category = arxiv_id.split("/")[0]
                tags = [category, "arxiv"]
            else:
                tags = ["arxiv", "cs.AI"]  # Default to AI category
        else:
            tags = ["arxiv"]

        # Add paper-specific metadata
        metadata["type"] = "research_paper"
        metadata["source_type"] = "preprint"

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
