"""News collectors package

This package contains various collectors for gathering news from different sources.
"""

from .base import BaseCollector
from .rss import RSSCollector

__all__ = ["BaseCollector", "RSSCollector"]
