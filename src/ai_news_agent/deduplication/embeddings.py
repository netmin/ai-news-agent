"""Embedding generation service for semantic similarity."""

import hashlib
from pathlib import Path

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer

from ..config import settings


class EmbeddingService:
    """Service for generating text embeddings.

    Uses sentence-transformers for efficient semantic similarity computation.
    Caches embeddings to disk for performance.
    """

    def __init__(self, model_name: str | None = None, cache_dir: Path | None = None):
        """Initialize embedding service.

        Args:
            model_name: Name of the sentence-transformer model to use
            cache_dir: Directory for caching embeddings
        """
        self.model_name = model_name or getattr(
            settings,
            "embedding_model",
            "all-MiniLM-L6-v2",  # Fast and good for news content
        )
        self.cache_dir = cache_dir or Path(
            getattr(settings, "embedding_cache_dir", ".embeddings_cache")
        )
        self.cache_dir.mkdir(exist_ok=True)

        self._model: SentenceTransformer | None = None
        self._embedding_dim: int | None = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            self._embedding_dim = self._model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded. Embedding dimension: {self._embedding_dim}")
        return self._model

    @property
    def embedding_dim(self) -> int:
        """Get embedding dimension."""
        if self._embedding_dim is None:
            _ = self.model  # Force model loading
        return self._embedding_dim

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Include model name in hash to avoid conflicts
        content = f"{self.model_name}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a cache key."""
        # Use subdirectories to avoid too many files in one directory
        subdir = cache_key[:2]
        return self.cache_dir / subdir / f"{cache_key}.npy"

    def _load_from_cache(self, cache_key: str) -> np.ndarray | None:
        """Load embedding from cache."""
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                return np.load(cache_path)
            except Exception as e:
                logger.warning(f"Failed to load embedding from cache: {e}")
                # Remove corrupted cache file
                cache_path.unlink(missing_ok=True)
        return None

    def _save_to_cache(self, cache_key: str, embedding: np.ndarray) -> None:
        """Save embedding to cache."""
        cache_path = self._get_cache_path(cache_key)
        cache_path.parent.mkdir(exist_ok=True)
        try:
            np.save(cache_path, embedding)
        except Exception as e:
            logger.warning(f"Failed to save embedding to cache: {e}")

    def encode(self, text: str, use_cache: bool = True) -> np.ndarray:
        """Generate embedding for text.

        Args:
            text: Text to encode
            use_cache: Whether to use caching

        Returns:
            Embedding vector as numpy array
        """
        if use_cache:
            cache_key = self._get_cache_key(text)
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                return cached

        # Generate embedding
        embedding = self.model.encode(text, convert_to_numpy=True)

        if use_cache:
            self._save_to_cache(cache_key, embedding)

        return embedding

    def encode_batch(self, texts: list[str], use_cache: bool = True) -> np.ndarray:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to encode
            use_cache: Whether to use caching

        Returns:
            Array of embeddings (shape: [len(texts), embedding_dim])
        """
        if not texts:
            return np.array([])

        embeddings = []
        texts_to_encode = []
        text_indices = []

        # Check cache first
        for i, text in enumerate(texts):
            if use_cache:
                cache_key = self._get_cache_key(text)
                cached = self._load_from_cache(cache_key)
                if cached is not None:
                    embeddings.append((i, cached))
                    continue

            texts_to_encode.append(text)
            text_indices.append(i)

        # Batch encode uncached texts
        if texts_to_encode:
            new_embeddings = self.model.encode(texts_to_encode, convert_to_numpy=True)

            # Cache new embeddings
            if use_cache:
                for text, embedding in zip(
                    texts_to_encode, new_embeddings, strict=False
                ):
                    cache_key = self._get_cache_key(text)
                    self._save_to_cache(cache_key, embedding)

            # Add to results
            for idx, embedding in zip(text_indices, new_embeddings, strict=False):
                embeddings.append((idx, embedding))

        # Sort by original index and extract embeddings
        embeddings.sort(key=lambda x: x[0])
        return np.array([emb for _, emb in embeddings])

    def cosine_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score (0-1)
        """
        # Normalize vectors
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)

        # Ensure result is in [0, 1] range
        return float((similarity + 1) / 2)

    def find_most_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray,
        threshold: float = 0.8,
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """Find most similar embeddings to query.

        Args:
            query_embedding: Query embedding
            candidate_embeddings: Array of candidate embeddings
            threshold: Minimum similarity threshold
            top_k: Return only top K results

        Returns:
            List of (index, similarity_score) tuples, sorted by similarity
        """
        if len(candidate_embeddings) == 0:
            return []

        # Vectorized cosine similarity calculation
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return []

        # Normalize query
        query_normalized = query_embedding / query_norm

        # Calculate similarities
        similarities = []
        for i, candidate in enumerate(candidate_embeddings):
            candidate_norm = np.linalg.norm(candidate)
            if candidate_norm == 0:
                continue

            # Normalized dot product
            similarity = np.dot(query_normalized, candidate / candidate_norm)
            # Convert to 0-1 range
            similarity = float((similarity + 1) / 2)

            if similarity >= threshold:
                similarities.append((i, similarity))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Limit to top_k if specified
        if top_k is not None:
            similarities = similarities[:top_k]

        return similarities

    def clear_cache(self) -> int:
        """Clear all cached embeddings.

        Returns:
            Number of cache files removed
        """
        count = 0
        for cache_file in self.cache_dir.rglob("*.npy"):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to remove cache file {cache_file}: {e}")

        logger.info(f"Cleared {count} embedding cache files")
        return count

    def combine_text_for_similarity(self, title: str, content: str, url: str) -> str:
        """Combine title, content, and URL for similarity comparison.

        Args:
            title: Article title
            content: Article content (will be truncated)
            url: Article URL

        Returns:
            Combined text optimized for similarity comparison
        """
        # Extract domain from URL for context
        from urllib.parse import urlparse

        try:
            domain = urlparse(url).netloc
        except Exception:
            domain = ""

        # Truncate content to focus on beginning
        max_content_length = 500
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        # Combine with weights (title is most important)
        combined = f"Title: {title}\n\nContent: {content}\n\nSource: {domain}"

        return combined
