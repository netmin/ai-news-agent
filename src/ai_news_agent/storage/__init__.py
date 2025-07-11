"""Storage module for persisting news items and related data."""

from .database import DatabaseManager, close_database, get_db_manager, init_database
from .models import Base, CollectorRunDB, DailyDigestDB, NewsItemDB, WeeklySummaryDB
from .repositories import (
    CollectorRepository,
    DeduplicationRepository,
    DigestRepository,
    NewsItemRepository,
)

__all__ = [
    "DatabaseManager",
    "get_db_manager",
    "init_database",
    "close_database",
    "Base",
    "NewsItemDB",
    "CollectorRunDB",
    "DailyDigestDB",
    "WeeklySummaryDB",
    "NewsItemRepository",
    "CollectorRepository",
    "DigestRepository",
    "DeduplicationRepository",
]
