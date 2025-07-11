"""Deduplication service for news items."""

from .embeddings import EmbeddingService
from .service import DeduplicationService

__all__ = ["DeduplicationService", "EmbeddingService"]
