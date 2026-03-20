"""
Project Nobi — Semantic Embedding Engine
==========================================
Generates and manages text embeddings for semantic memory search.

Supports two backends:
  1. sentence-transformers (all-MiniLM-L6-v2) — high quality, ~80MB model
  2. TF-IDF fallback — lightweight, no extra deps, decent quality

The engine lazy-loads models on first use and is thread-safe.
Embeddings are numpy arrays stored as BLOBs in SQLite.
"""

import logging
import threading
from typing import List, Optional, Union

import numpy as np

logger = logging.getLogger("nobi-memory")

# ── Sentinel for checking availability ────────────────────────────────────────

_SENTENCE_TRANSFORMERS_AVAILABLE = None  # Lazy check


def _check_sentence_transformers() -> bool:
    """Check if sentence-transformers is installed (cached)."""
    global _SENTENCE_TRANSFORMERS_AVAILABLE
    if _SENTENCE_TRANSFORMERS_AVAILABLE is None:
        try:
            import sentence_transformers  # noqa: F401
            _SENTENCE_TRANSFORMERS_AVAILABLE = True
        except ImportError:
            _SENTENCE_TRANSFORMERS_AVAILABLE = False
    return _SENTENCE_TRANSFORMERS_AVAILABLE


# ── Embedding Engine ──────────────────────────────────────────────────────────


class EmbeddingEngine:
    """
    Thread-safe embedding generator with lazy model loading.

    Usage:
        engine = EmbeddingEngine()
        vec = engine.embed("Hello world")        # single text
        vecs = engine.embed_batch(["a", "b"])     # batch
        sim = engine.cosine_similarity(vec1, vec2)
    """

    # Default model for sentence-transformers
    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    # Embedding dimension for the default model
    EMBEDDING_DIM = 384

    def __init__(self, model_name: Optional[str] = None, force_tfidf: bool = False):
        """
        Initialize the embedding engine.

        Args:
            model_name: sentence-transformers model name (default: all-MiniLM-L6-v2)
            force_tfidf: Force TF-IDF backend even if sentence-transformers is available
        """
        self._model_name = model_name or self.DEFAULT_MODEL
        self._force_tfidf = force_tfidf
        self._lock = threading.Lock()
        self._model = None
        self._tfidf_vectorizer = None
        self._backend: Optional[str] = None  # 'sbert' or 'tfidf'

    @property
    def backend(self) -> str:
        """Return the active backend name, initializing if needed."""
        if self._backend is None:
            self._ensure_loaded()
        return self._backend

    @property
    def dimension(self) -> int:
        """Return embedding dimension for the active backend."""
        if self._backend == "sbert":
            return self.EMBEDDING_DIM
        # TF-IDF dimension varies; return after fitting
        if self._tfidf_vectorizer is not None and hasattr(self._tfidf_vectorizer, "vocabulary_"):
            return len(self._tfidf_vectorizer.vocabulary_)
        return 0  # Not yet fitted

    def _ensure_loaded(self):
        """Lazy-load the model on first use. Thread-safe."""
        if self._backend is not None:
            return

        with self._lock:
            # Double-check after acquiring lock
            if self._backend is not None:
                return

            if not self._force_tfidf and _check_sentence_transformers():
                try:
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(self._model_name)
                    self._backend = "sbert"
                    logger.info(
                        f"[Embeddings] Loaded sentence-transformers model: {self._model_name}"
                    )
                    return
                except Exception as e:
                    logger.warning(
                        f"[Embeddings] Failed to load sentence-transformers: {e}. "
                        "Falling back to TF-IDF."
                    )

            # Fallback: TF-IDF
            self._init_tfidf()
            self._backend = "tfidf"
            logger.info("[Embeddings] Using TF-IDF fallback backend")

    def _init_tfidf(self):
        """Initialize TF-IDF vectorizer with reasonable defaults."""
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._tfidf_vectorizer = TfidfVectorizer(
            max_features=384,  # Match sbert dimension for consistency
            ngram_range=(1, 2),
            sublinear_tf=True,
            strip_accents="unicode",
            stop_words="english",
        )
        # Fit with a small seed corpus so it works immediately
        seed_corpus = [
            "the user likes music and plays guitar",
            "the user lives in a city and works as an engineer",
            "the user has a pet dog named buddy",
            "the user enjoys cooking italian food",
            "the user is feeling happy today",
            "the user mentioned their family and friends",
            "important personal information about preferences",
            "event happening this week travel plans",
            "emotional state feeling stressed about work",
            "fact about user age birthday location",
        ]
        self._tfidf_vectorizer.fit(seed_corpus)

    def embed(self, text: str) -> np.ndarray:
        """
        Generate an embedding vector for a single text.

        Args:
            text: Input text to embed

        Returns:
            numpy array of shape (dim,)
        """
        self._ensure_loaded()

        if not text or not text.strip():
            return np.zeros(self.EMBEDDING_DIM if self._backend == "sbert" else 384)

        if self._backend == "sbert":
            return self._model.encode(text, normalize_embeddings=True, show_progress_bar=False)

        # TF-IDF fallback
        return self._tfidf_embed(text)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for a batch of texts (more efficient for sbert).

        Args:
            texts: List of input texts

        Returns:
            List of numpy arrays
        """
        self._ensure_loaded()

        if not texts:
            return []

        # Filter empty strings
        clean_texts = [t if t and t.strip() else "" for t in texts]

        if self._backend == "sbert":
            embeddings = self._model.encode(
                clean_texts, normalize_embeddings=True,
                show_progress_bar=False, batch_size=32,
            )
            return [emb for emb in embeddings]

        # TF-IDF fallback — process individually
        return [self._tfidf_embed(t) for t in clean_texts]

    def _tfidf_embed(self, text: str) -> np.ndarray:
        """Generate a TF-IDF embedding, handling unseen vocabulary gracefully."""
        if not text or not text.strip():
            dim = len(self._tfidf_vectorizer.vocabulary_) if hasattr(self._tfidf_vectorizer, "vocabulary_") else 384
            return np.zeros(dim)

        try:
            vec = self._tfidf_vectorizer.transform([text]).toarray()[0]
            # Normalize to unit vector for cosine similarity
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec.astype(np.float32)
        except Exception as e:
            logger.warning(f"[Embeddings] TF-IDF error: {e}")
            dim = len(self._tfidf_vectorizer.vocabulary_) if hasattr(self._tfidf_vectorizer, "vocabulary_") else 384
            return np.zeros(dim)

    def refit_tfidf(self, corpus: List[str]):
        """
        Refit the TF-IDF vectorizer with a new corpus (e.g., all existing memories).
        Only works for TF-IDF backend. This invalidates existing TF-IDF embeddings.

        Args:
            corpus: List of texts to fit on
        """
        if self._backend != "tfidf" or not self._tfidf_vectorizer:
            return

        if not corpus:
            return

        with self._lock:
            self._tfidf_vectorizer.fit(corpus)
            logger.info(f"[Embeddings] Refit TF-IDF on {len(corpus)} documents")

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Similarity score in [-1, 1], typically [0, 1] for normalized vectors
        """
        if a is None or b is None:
            return 0.0

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    @staticmethod
    def serialize_embedding(embedding: np.ndarray) -> bytes:
        """
        Serialize a numpy embedding to bytes for SQLite BLOB storage.

        Args:
            embedding: numpy array

        Returns:
            bytes representation
        """
        return embedding.astype(np.float32).tobytes()

    @staticmethod
    def deserialize_embedding(data: bytes, dim: int = 384) -> Optional[np.ndarray]:
        """
        Deserialize bytes from SQLite BLOB back to numpy array.

        Args:
            data: bytes from SQLite
            dim: expected dimension (default 384 for all-MiniLM-L6-v2)

        Returns:
            numpy array or None if data is invalid
        """
        if not data:
            return None
        try:
            arr = np.frombuffer(data, dtype=np.float32)
            if arr.size == 0:
                return None
            return arr
        except Exception as e:
            logger.warning(f"[Embeddings] Deserialization error: {e}")
            return None


# ── Module-level singleton ────────────────────────────────────────────────────

_default_engine: Optional[EmbeddingEngine] = None
_engine_lock = threading.Lock()


def get_engine(force_tfidf: bool = False) -> EmbeddingEngine:
    """
    Get or create the module-level singleton EmbeddingEngine.

    Args:
        force_tfidf: Force TF-IDF even if sentence-transformers is available

    Returns:
        EmbeddingEngine instance
    """
    global _default_engine
    if _default_engine is None:
        with _engine_lock:
            if _default_engine is None:
                _default_engine = EmbeddingEngine(force_tfidf=force_tfidf)
    return _default_engine


def reset_engine():
    """Reset the singleton engine (useful for testing)."""
    global _default_engine, _SENTENCE_TRANSFORMERS_AVAILABLE
    with _engine_lock:
        _default_engine = None
    _SENTENCE_TRANSFORMERS_AVAILABLE = None
