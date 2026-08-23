"""
Unit tests for the embeddings module.

Tests that load the sentence-transformers model are marked @pytest.mark.slow.
"""


import numpy as np
import pytest

from phantom.core.embeddings import EmbeddingGenerator, EmbeddingResult

pytestmark = pytest.mark.unit


class TestEmbeddingGeneratorInit:
    """Test initialization without loading the model."""

    def test_default_model_name(self):
        gen = EmbeddingGenerator()
        assert gen.model_name == "all-MiniLM-L6-v2"
        assert gen.device == "cpu"

    def test_custom_model_name(self):
        gen = EmbeddingGenerator(model_name="custom-model", device="cuda")
        assert gen.model_name == "custom-model"
        assert gen.device == "cuda"

    def test_model_not_loaded_initially(self):
        gen = EmbeddingGenerator()
        assert gen._model is None
        assert gen._dimension is None


class TestEmbeddingResult:
    """Test the EmbeddingResult dataclass."""

    def test_construction(self):
        emb = np.zeros((3, 384), dtype=np.float32)
        result = EmbeddingResult(
            embeddings=emb,
            model="all-MiniLM-L6-v2",
            dimension=384,
            count=3,
        )
        assert result.model == "all-MiniLM-L6-v2"
        assert result.dimension == 384
        assert result.count == 3
        assert result.embeddings.shape == (3, 384)


@pytest.mark.slow
class TestEmbeddingGeneratorWithModel:
    """Tests that actually load sentence-transformers."""

    def test_lazy_loading(self):
        gen = EmbeddingGenerator()
        assert gen._model is None
        _ = gen.model  # triggers load
        assert gen._model is not None

    def test_dimension(self):
        gen = EmbeddingGenerator()
        assert gen.dimension == 384

    def test_encode_batch(self):
        gen = EmbeddingGenerator()
        texts = ["Hello world", "Test sentence"]
        embeddings = gen.encode(texts)
        assert embeddings.shape == (2, 384)
        assert embeddings.dtype == np.float32

    def test_encode_single(self):
        gen = EmbeddingGenerator()
        embedding = gen.encode_single("Test")
        assert embedding.shape == (384,)

    def test_encode_with_metadata(self):
        gen = EmbeddingGenerator()
        result = gen.encode_with_metadata(["a", "b", "c"])
        assert isinstance(result, EmbeddingResult)
        assert result.count == 3
        assert result.dimension == 384
        assert result.embeddings.shape == (3, 384)

    def test_normalized_embeddings(self):
        gen = EmbeddingGenerator()
        embedding = gen.encode_single("Test", normalize=True)
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 0.01
