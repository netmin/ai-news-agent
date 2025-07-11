"""News item ranking for digest generation."""

from collections import Counter
from datetime import UTC, datetime

import numpy as np
from loguru import logger

from ..config import settings
from ..models import NewsItem


class NewsRanker:
    """Ranks news items for inclusion in digests.

    Uses multiple signals to determine importance:
    - Recency (newer items score higher)
    - Source diversity (avoid too many items from same source)
    - Tag relevance (matches user-defined important tags)
    - Content length (prefer substantial articles)
    - Uniqueness (avoid similar items)
    """

    def __init__(
        self,
        recency_weight: float = 0.3,
        diversity_weight: float = 0.2,
        relevance_weight: float = 0.3,
        length_weight: float = 0.2,
    ):
        """Initialize ranker with scoring weights.

        Args:
            recency_weight: Weight for time-based scoring
            diversity_weight: Weight for source diversity
            relevance_weight: Weight for tag relevance
            length_weight: Weight for content length
        """
        self.recency_weight = recency_weight
        self.diversity_weight = diversity_weight
        self.relevance_weight = relevance_weight
        self.length_weight = length_weight

        # Normalize weights
        total = sum(
            [
                self.recency_weight,
                self.diversity_weight,
                self.relevance_weight,
                self.length_weight,
            ]
        )
        self.recency_weight /= total
        self.diversity_weight /= total
        self.relevance_weight /= total
        self.length_weight /= total

        # Load important tags from settings
        self.important_tags = set(
            getattr(
                settings,
                "important_tags",
                ["breaking", "important", "security", "ai", "technology"],
            )
        )

    def rank_items(
        self,
        items: list[NewsItem],
        max_items: int = 20,
        max_per_source: int = 3,
        reference_time: datetime | None = None,
    ) -> list[tuple[NewsItem, float]]:
        """Rank news items and return top selections.

        Args:
            items: List of news items to rank
            max_items: Maximum items to return
            max_per_source: Maximum items per source
            reference_time: Time to use for recency calculation

        Returns:
            List of (item, score) tuples, sorted by score descending
        """
        if not items:
            return []

        reference_time = reference_time or datetime.now(UTC)

        # Calculate individual scores
        scored_items = []
        for item in items:
            score = self._calculate_score(item, reference_time, items)
            scored_items.append((item, score))

        # Sort by score
        scored_items.sort(key=lambda x: x[1], reverse=True)

        # Apply source diversity filter
        selected = []
        source_counts = Counter()

        for item, score in scored_items:
            if source_counts[item.source] < max_per_source:
                selected.append((item, score))
                source_counts[item.source] += 1

                if len(selected) >= max_items:
                    break

        logger.info(
            f"Ranked {len(items)} items, selected top {len(selected)} "
            f"with scores {selected[0][1]:.3f} to {selected[-1][1]:.3f}"
        )

        return selected

    def _calculate_score(
        self,
        item: NewsItem,
        reference_time: datetime,
        all_items: list[NewsItem],
    ) -> float:
        """Calculate ranking score for a single item.

        Args:
            item: News item to score
            reference_time: Reference time for recency
            all_items: All items being ranked (for diversity)

        Returns:
            Combined score (0-1)
        """
        # Recency score (exponential decay)
        hours_old = (reference_time - item.published_at).total_seconds() / 3600
        recency_score = np.exp(-hours_old / 24)  # Half-life of 24 hours

        # Relevance score based on tags
        relevance_score = 0.0
        if item.tags:
            matching_tags = set(item.tags) & self.important_tags
            if matching_tags:
                relevance_score = min(1.0, len(matching_tags) / 2)  # Cap at 2 matches

        # Length score (prefer medium-length content)
        content_length = len(item.content)
        if content_length < 100:
            length_score = 0.1
        elif content_length < 500:
            length_score = 0.5
        elif content_length < 2000:
            length_score = 1.0
        else:
            length_score = 0.8  # Very long might be less digestible

        # Diversity score (inverse of source frequency)
        source_count = sum(1 for i in all_items if i.source == item.source)
        diversity_score = 1.0 / (1 + np.log(source_count))

        # Combine scores
        total_score = (
            self.recency_weight * recency_score
            + self.relevance_weight * relevance_score
            + self.length_weight * length_score
            + self.diversity_weight * diversity_score
        )

        return total_score

    def group_by_category(
        self, ranked_items: list[tuple[NewsItem, float]]
    ) -> dict[str, list[tuple[NewsItem, float]]]:
        """Group ranked items by category/tags.

        Args:
            ranked_items: List of (item, score) tuples

        Returns:
            Dict mapping category to list of items
        """
        categories = {}

        for item, score in ranked_items:
            # Determine primary category
            if not item.tags:
                category = "general"
            else:
                # Use first tag as category, with some normalization
                primary_tag = item.tags[0].lower()

                # Map similar tags to common categories
                if primary_tag in [
                    "ai",
                    "ml",
                    "machine-learning",
                    "artificial-intelligence",
                ]:
                    category = "ai"
                elif primary_tag in ["security", "cybersecurity", "vulnerability"]:
                    category = "security"
                elif primary_tag in ["tech", "technology", "software", "hardware"]:
                    category = "technology"
                elif primary_tag in ["science", "research", "study"]:
                    category = "science"
                elif primary_tag in ["business", "finance", "economy"]:
                    category = "business"
                else:
                    category = primary_tag

            if category not in categories:
                categories[category] = []
            categories[category].append((item, score))

        return categories

    def get_top_topics(
        self, items: list[NewsItem], limit: int = 5
    ) -> list[tuple[str, int]]:
        """Extract top topics/tags from items.

        Args:
            items: List of news items
            limit: Maximum topics to return

        Returns:
            List of (topic, count) tuples
        """
        tag_counts = Counter()

        for item in items:
            if item.tags:
                tag_counts.update(item.tags)

        return tag_counts.most_common(limit)
