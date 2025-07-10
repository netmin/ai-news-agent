"""Base parser interface for RSS feed parsers"""

from abc import ABC, abstractmethod
from datetime import datetime

from ...models import NewsItem


class BaseParser(ABC):
    """Abstract base class for RSS feed parsers

    Different RSS feeds have different formats and structures.
    This base class ensures all parsers provide a consistent interface.
    """

    def __init__(self, source_name: str):
        """Initialize parser with source name

        Args:
            source_name: Name of the RSS feed source
        """
        self.source_name = source_name

    @abstractmethod
    async def parse(self, content: str) -> list[NewsItem]:
        """Parse RSS feed content into NewsItem objects

        Args:
            content: Raw RSS/XML content as string

        Returns:
            List of validated NewsItem objects

        Note:
            Should handle parsing errors gracefully and
            skip invalid items rather than failing entirely
        """
        pass

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse various date formats into datetime

        Args:
            date_str: Date string in various formats

        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not date_str:
            return None

        from dateutil import parser as date_parser

        try:
            # dateutil.parser handles most common date formats
            return date_parser.parse(date_str)
        except (ValueError, TypeError):
            return None

    def _clean_html(self, text: str | None) -> str:
        """Remove HTML tags from text

        Args:
            text: Text potentially containing HTML

        Returns:
            Clean text without HTML tags
        """
        if not text:
            return ""

        from bs4 import BeautifulSoup

        # Parse HTML and extract text
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(strip=True)
