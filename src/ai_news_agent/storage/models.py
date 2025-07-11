"""SQLAlchemy models for database persistence."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class NewsItemDB(Base):
    """Database model for news items."""

    __tablename__ = "news_items"

    id = Column(String(64), primary_key=True)  # SHA256 hash
    url = Column(String(2048), nullable=False)
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    source = Column(String(128), nullable=False)
    published_at = Column(DateTime, nullable=False)
    collected_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    tags = Column(JSON, nullable=False, default=list)
    extra_metadata = Column(JSON, nullable=False, default=dict)
    is_duplicate = Column(Boolean, nullable=False, default=False)
    duplicate_of = Column(String(64), nullable=True)

    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_published_at", "published_at"),
        Index("idx_collected_at", "collected_at"),
        Index("idx_source", "source"),
        Index("idx_is_duplicate", "is_duplicate"),
        UniqueConstraint("url", name="uq_news_item_url"),
    )

    # Relationships
    collector_runs = relationship(
        "CollectorRunDB", secondary="collector_run_items", back_populates="items"
    )
    digest_entries = relationship("DigestEntryDB", back_populates="news_item")


class CollectorRunDB(Base):
    """Database model for collector run statistics."""

    __tablename__ = "collector_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collector_type = Column(String(64), nullable=False)  # e.g., "rss"
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)
    total_items = Column(Integer, nullable=False, default=0)
    new_items = Column(Integer, nullable=False, default=0)
    duplicate_items = Column(Integer, nullable=False, default=0)
    failed_sources = Column(JSON, nullable=False, default=list)
    statistics = Column(JSON, nullable=False, default=dict)

    # Indexes
    __table_args__ = (
        Index("idx_collector_type", "collector_type"),
        Index("idx_started_at", "started_at"),
    )

    # Relationships
    items = relationship(
        "NewsItemDB", secondary="collector_run_items", back_populates="collector_runs"
    )


# Association table for many-to-many relationship
collector_run_items = Base.metadata.tables.get("collector_run_items")
if not collector_run_items:
    from sqlalchemy import Table

    collector_run_items = Table(
        "collector_run_items",
        Base.metadata,
        Column("collector_run_id", Integer, ForeignKey("collector_runs.id")),
        Column("news_item_id", String(64), ForeignKey("news_items.id")),
        Index("idx_collector_run_id", "collector_run_id"),
        Index("idx_news_item_id", "news_item_id"),
    )


class DailyDigestDB(Base):
    """Database model for daily digests."""

    __tablename__ = "daily_digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    sent_at = Column(DateTime, nullable=True)
    item_count = Column(Integer, nullable=False, default=0)
    content_markdown = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    extra_metadata = Column(JSON, nullable=False, default=dict)
    is_sent = Column(Boolean, nullable=False, default=False)

    # Indexes
    __table_args__ = (
        Index("idx_digest_date", "date"),
        Index("idx_digest_sent", "is_sent"),
    )

    # Relationships
    entries = relationship("DigestEntryDB", back_populates="daily_digest")


class WeeklySummaryDB(Base):
    """Database model for weekly summaries."""

    __tablename__ = "weekly_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_start = Column(DateTime, nullable=False)
    week_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    sent_at = Column(DateTime, nullable=True)
    item_count = Column(Integer, nullable=False, default=0)
    content_markdown = Column(Text, nullable=True)
    content_html = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    top_topics = Column(JSON, nullable=False, default=list)
    extra_metadata = Column(JSON, nullable=False, default=dict)
    is_sent = Column(Boolean, nullable=False, default=False)

    # Indexes
    __table_args__ = (
        Index("idx_week_start", "week_start"),
        Index("idx_week_end", "week_end"),
        Index("idx_weekly_sent", "is_sent"),
        UniqueConstraint("week_start", "week_end", name="uq_weekly_period"),
    )

    # Relationships
    entries = relationship("DigestEntryDB", back_populates="weekly_summary")


class DigestEntryDB(Base):
    """Database model for digest entries (links news items to digests)."""

    __tablename__ = "digest_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    news_item_id = Column(String(64), ForeignKey("news_items.id"), nullable=False)
    daily_digest_id = Column(Integer, ForeignKey("daily_digests.id"), nullable=True)
    weekly_summary_id = Column(
        Integer, ForeignKey("weekly_summaries.id"), nullable=True
    )
    ranking_score = Column(Float, nullable=True)
    inclusion_reason = Column(String(256), nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_entry_news_item", "news_item_id"),
        Index("idx_entry_daily", "daily_digest_id"),
        Index("idx_entry_weekly", "weekly_summary_id"),
    )

    # Relationships
    news_item = relationship("NewsItemDB", back_populates="digest_entries")
    daily_digest = relationship("DailyDigestDB", back_populates="entries")
    weekly_summary = relationship("WeeklySummaryDB", back_populates="entries")


class DeduplicationCacheDB(Base):
    """Database model for deduplication cache."""

    __tablename__ = "deduplication_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url_hash = Column(String(64), nullable=False, unique=True)
    title_hash = Column(String(64), nullable=False)
    content_hash = Column(String(64), nullable=False)
    first_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    last_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    occurrence_count = Column(Integer, nullable=False, default=1)
    news_item_id = Column(String(64), ForeignKey("news_items.id"), nullable=False)

    # Indexes for fast deduplication lookups
    __table_args__ = (
        Index("idx_url_hash", "url_hash"),
        Index("idx_title_hash", "title_hash"),
        Index("idx_content_hash", "content_hash"),
        Index("idx_first_seen", "first_seen_at"),
    )
