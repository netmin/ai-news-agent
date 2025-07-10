"""Base collector abstract class for all news collectors"""

from abc import ABC, abstractmethod

from ..models import CollectorStats, NewsItem


class BaseCollector(ABC):
    """Abstract base class for news collectors

    All collectors must implement the collect() and get_stats() methods.
    This ensures a consistent interface for different news sources.
    """

    @abstractmethod
    async def collect(self) -> list[NewsItem]:
        """Collect news items from source

        Returns:
            List of validated NewsItem objects

        Raises:
            Should handle all errors gracefully and log them,
            returning partial results if some sources fail
        """
        pass

    @abstractmethod
    async def get_stats(self) -> list[CollectorStats]:
        """Get collector performance statistics

        Returns:
            List of CollectorStats objects, one per source

        Note:
            Statistics should include success/failure counts,
            response times, and health status
        """
        pass
