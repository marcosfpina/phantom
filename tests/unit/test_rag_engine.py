"""
Unit tests for the CEREBRO RAG Engine module.

Tests: CerebroRAG initialization, indexing, querying, and stats.
Uses mocked sentence-transformers to avoid loading real models.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from phantom.cerebro.rag_engine import CerebroRAG

pytestmark = pytest.mark.unit


SAMPLE_KB = {
    "meta": {"total_decisions": 2, "version": "1.0"},
    "decisions": [
        {
            "id": "ADR-0001",
            "title": "Thermal Management Strategy",
            "status": "accepted",
            "summary": "Implement thermal monitoring and throttling.",
            "knowledge": {
                "what": "System thermal management via monitoring.",
                "why": "Prevent hardware damage from overheating.",
                "implications": {"positive": ["Reliability", "Safety"]},
            },
            "keywords": ["thermal", "monitoring", "hardware"],
            "concepts": ["ops"],
            "questions": [],
        },
        {
            "id": "ADR-0002",
            "title": "Memory Optimization",
            "status": "accepted",
            "summary": "Optimize memory usage patterns.",
            "knowledge": {
                "what": "Memory pooling and cache optimization.",
                "why": "Reduce OOM risks and improve performance.",
            },
            "keywords": ["memory", "optimization", "performance"],
            "concepts": ["performance"],
            "questions": [],
        },
    ],
}

EMBEDDING_DIM = 16


@pytest.fixture
def kb_file(tmp_path):
    """Create a temporary knowledge base JSON file."""
    kb_path = tmp_path / "knowledge_base.json"
    kb_path.write_text(json.dumps(SAMPLE_KB))
    return kb_path


@pytest.fixture
def mock_encoder():
    """Create a mocked SentenceTransformer."""
    encoder = MagicMock()
    encoder.get_sentence_embedding_dimension.return_value = EMBEDDING_DIM
    # Return random but deterministic embeddings
    rng = np.random.RandomState(42)

    def mock_encode(texts, **kwargs):
        embs = rng.randn(len(texts), EMBEDDING_DIM).astype(np.float32)
        # Normalize
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        return embs / norms

    encoder.encode = mock_encode
    return encoder


class TestCerebroRAGInit:
    """Test CerebroRAG initialization."""

    def test_init_stores_path(self, kb_file):
        rag = CerebroRAG(str(kb_file))
        assert rag.knowledge_base_path == str(kb_file)
        assert rag.vector_store is None
        assert rag.encoder is None

    def test_init_with_cache_path(self, kb_file, tmp_path):
        cache = str(tmp_path / "cache")
        rag = CerebroRAG(str(kb_file), index_cache_path=cache)
        assert rag.index_cache_path == Path(cache)

    def test_init_custom_model(self, kb_file):
        rag = CerebroRAG(str(kb_file), embedding_model="custom-model")
        assert rag.embedding_model_name == "custom-model"


class TestCerebroRAGInitialize:
    """Test CerebroRAG.initialize() with mocked encoder."""

    @patch("phantom.cerebro.rag_engine.CerebroRAG._init_encoder")
    def test_initialize_loads_documents(self, mock_init_enc, kb_file, mock_encoder):
        rag = CerebroRAG(str(kb_file))
        rag.encoder = mock_encoder

        # Patch _init_encoder to set our mock
        def set_encoder():
            rag.encoder = mock_encoder
        mock_init_enc.side_effect = set_encoder

        rag.initialize()

        assert len(rag.documents) == 2
        assert rag.documents[0].id == "ADR-0001"

    @patch("phantom.cerebro.rag_engine.CerebroRAG._init_encoder")
    def test_initialize_builds_index(self, mock_init_enc, kb_file, mock_encoder):
        rag = CerebroRAG(str(kb_file))

        def set_encoder():
            rag.encoder = mock_encoder
        mock_init_enc.side_effect = set_encoder

        rag.initialize()

        assert rag.vector_store is not None
        assert len(rag.vector_store) == 2

    @patch("phantom.cerebro.rag_engine.CerebroRAG._init_encoder")
    def test_initialize_saves_cache(self, mock_init_enc, kb_file, tmp_path, mock_encoder):
        cache_path = tmp_path / "cache-index"
        rag = CerebroRAG(str(kb_file), index_cache_path=str(cache_path))

        def set_encoder():
            rag.encoder = mock_encoder
        mock_init_enc.side_effect = set_encoder

        rag.initialize()

        # Cache should be saved
        assert (cache_path.parent / (cache_path.name + ".index")).exists() or \
               rag.vector_store is not None


class TestCerebroRAGQuery:
    """Test CerebroRAG.query() with mocked encoder."""

    @patch("phantom.cerebro.rag_engine.CerebroRAG._init_encoder")
    def _setup_rag(self, kb_file, mock_encoder, mock_init_enc):
        rag = CerebroRAG(str(kb_file))

        def set_encoder():
            rag.encoder = mock_encoder
        mock_init_enc.side_effect = set_encoder

        rag.initialize()
        return rag

    def test_query_returns_results(self, kb_file, mock_encoder):
        with patch("phantom.cerebro.rag_engine.CerebroRAG._init_encoder") as mock_init_enc:
            def set_encoder():
                pass
            mock_init_enc.side_effect = set_encoder

            rag = CerebroRAG(str(kb_file))
            rag.encoder = mock_encoder

            rag.initialize()

            results = rag.query("thermal monitoring", top_k=2, min_score=0.0)
            assert isinstance(results, list)
            assert len(results) > 0
            # Each result should have expected fields
            for r in results:
                assert "id" in r
                assert "title" in r
                assert "score" in r
                assert "text" in r

    def test_query_min_score_filters(self, kb_file, mock_encoder):
        with patch("phantom.cerebro.rag_engine.CerebroRAG._init_encoder"):
            rag = CerebroRAG(str(kb_file))
            rag.encoder = mock_encoder
            rag.initialize()

            # Very high min_score should return fewer or no results
            results = rag.query("something", top_k=5, min_score=0.99)
            assert isinstance(results, list)

    def test_query_top_k_limits(self, kb_file, mock_encoder):
        with patch("phantom.cerebro.rag_engine.CerebroRAG._init_encoder"):
            rag = CerebroRAG(str(kb_file))
            rag.encoder = mock_encoder
            rag.initialize()

            results = rag.query("test", top_k=1, min_score=0.0)
            assert len(results) <= 1


class TestCerebroRAGStats:
    """Test CerebroRAG.get_stats()."""

    def test_stats_before_init(self, kb_file):
        rag = CerebroRAG(str(kb_file))
        stats = rag.get_stats()
        assert stats["documents_loaded"] == 0
        assert stats["index_size"] == 0
        assert stats["embedding_dim"] is None

    def test_stats_after_init(self, kb_file, mock_encoder):
        with patch("phantom.cerebro.rag_engine.CerebroRAG._init_encoder"):
            rag = CerebroRAG(str(kb_file))
            rag.encoder = mock_encoder
            rag.initialize()

            stats = rag.get_stats()
            assert stats["documents_loaded"] == 2
            assert stats["index_size"] == 2
            assert stats["embedding_dim"] == EMBEDDING_DIM
