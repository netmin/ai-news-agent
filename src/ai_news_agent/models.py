"""Pydantic models for data validation"""

import hashlib
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class NewsStatus(str, Enum):
    """Status of a news item"""

    NEW = "new"
    DUPLICATE = "duplicate"
    PROCESSED = "processed"
    FAILED = "failed"


class NewsItem(BaseModel):
    """Core news item model with validation"""

    id: str | None = Field(default=None, description="SHA256 hash of URL+title")
    url: HttpUrl = Field(description="Original article URL")
    title: str = Field(min_length=1, description="Article title")
    content: str = Field(default="", description="Full article content")
    summary: str = Field(default="", description="Brief summary")
    source: str = Field(description="Source feed name")
    published_at: datetime = Field(description="Publication timestamp")
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Collection timestamp",
    )
    tags: list[str] = Field(default_factory=list, description="Article tags")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra data")

    @model_validator(mode="after")
    def generate_id(self) -> Self:
        """Generate ID from URL and title if not provided"""
        if not self.id:
            content = f"{self.url}{self.title}".encode()
            self.id = hashlib.sha256(content).hexdigest()
        return self

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v: list[str]) -> list[str]:
        """Clean and deduplicate tags"""
        if not v:
            return []
        return list(set(tag.lower().strip() for tag in v if tag.strip()))

    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat(), HttpUrl: lambda v: str(v)}
    }


class DuplicationResult(BaseModel):
    """Result of deduplication check"""

    is_duplicate: bool
    similarity_score: float = Field(ge=0.0, le=1.0)
    matched_item_id: str | None = None
    reason: str | None = None


class DailyDigest(BaseModel):
    """Daily digest model"""

    date: datetime
    items: list[NewsItem]
    total_collected: int
    duplicates_found: int
    sources_summary: dict[str, int]
    top_tags: list[tuple[str, int]]

    @property
    def unique_items(self) -> int:
        return self.total_collected - self.duplicates_found


class WeeklySummary(BaseModel):
    """Weekly summary model"""

    week_number: int
    year: int
    start_date: datetime
    end_date: datetime
    total_items: int
    unique_stories: int
    top_stories: list[NewsItem]
    trending_topics: list[tuple[str, int]]
    most_active_day: tuple[str, int]
    sources_breakdown: dict[str, int]


class CollectorStats(BaseModel):
    """Statistics for collector performance"""

    source: str
    success_count: int = 0
    failure_count: int = 0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    average_items: float = 0.0
    average_response_time: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def health_status(self) -> str:
        if self.success_rate >= 0.9:
            return "healthy"
        elif self.success_rate >= 0.7:
            return "degraded"
        else:
            return "unhealthy"
