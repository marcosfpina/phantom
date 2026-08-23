"""
Unit tests for CORTEX v2.0 components: chunking and embeddings.

Tests that load sentence-transformers models are marked @pytest.mark.slow.
"""

import pytest

from phantom.rag.cortex_chunker import ChunkStrategy, MarkdownChunker

pytestmark = pytest.mark.unit

TEST_DOCUMENT = """# Python Error Handling Guide

## Introduction

Error handling is crucial for robust applications. Python provides several mechanisms for handling errors gracefully.

## Try-Except Blocks

The most common way to handle errors in Python is using try-except blocks:

```python
try:
    result = 10 / 0
except ZeroDivisionError:
    print("Cannot divide by zero")
```

## Multiple Exception Types

You can catch multiple exception types:

```python
try:
    value = int("not a number")
except (ValueError, TypeError) as e:
    print(f"Error: {e}")
```

## Finally Clause

Use finally for cleanup code that must run:

```python
try:
    file = open("data.txt")
    # process file
finally:
    file.close()
```

## Best Practices

1. Catch specific exceptions, not generic Exception
2. Use logging instead of print statements
3. Clean up resources in finally blocks
4. Don't use exceptions for flow control

## Context Managers

Modern Python prefers context managers:

```python
with open("data.txt") as file:
    content = file.read()
# File automatically closed
```

## Custom Exceptions

Define custom exceptions for domain-specific errors:

```python
class InvalidUserError(Exception):
    pass

def validate_user(user):
    if not user:
        raise InvalidUserError("User cannot be empty")
```

## Conclusion

Proper error handling makes your code more reliable and maintainable.
"""


class TestChunkingStrategies:
    """Test all chunking strategies produce valid output."""

    @pytest.mark.parametrize(
        "strategy",
        [ChunkStrategy.RECURSIVE, ChunkStrategy.SLIDING, ChunkStrategy.SIMPLE],
    )
    def test_strategy_produces_chunks(self, strategy):
        chunker = MarkdownChunker(strategy=strategy, max_tokens=200, overlap=50)
        chunks = chunker.chunk_text(TEST_DOCUMENT, source_file="test.md")
        assert len(chunks) > 0

    @pytest.mark.parametrize(
        "strategy",
        [ChunkStrategy.RECURSIVE, ChunkStrategy.SLIDING, ChunkStrategy.SIMPLE],
    )
    def test_strategy_chunks_have_tokens(self, strategy):
        chunker = MarkdownChunker(strategy=strategy, max_tokens=200, overlap=50)
        chunks = chunker.chunk_text(TEST_DOCUMENT, source_file="test.md")
        assert all(chunk.metadata.token_count > 0 for chunk in chunks)

    def test_stats_keys(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.RECURSIVE, max_tokens=200)
        chunks = chunker.chunk_text(TEST_DOCUMENT, source_file="test.md")
        stats = chunker.get_stats(chunks)
        assert "num_chunks" in stats
        assert "total_tokens" in stats
        assert "avg_tokens_per_chunk" in stats
        assert stats["total_tokens"] > 0


class TestChunkMetadata:
    """Test chunk metadata preservation."""

    def test_chunk_ids_are_sequential(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.RECURSIVE, max_tokens=200)
        chunks = chunker.chunk_text(TEST_DOCUMENT, source_file="test.md")
        ids = [chunk.metadata.chunk_id for chunk in chunks]
        assert ids == list(range(len(chunks)))

    def test_source_file_preserved(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.RECURSIVE, max_tokens=200)
        chunks = chunker.chunk_text(TEST_DOCUMENT, source_file="test.md")
        assert all(chunk.metadata.source_file == "test.md" for chunk in chunks)

    def test_word_count_positive(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.RECURSIVE, max_tokens=200)
        chunks = chunker.chunk_text(TEST_DOCUMENT, source_file="test.md")
        assert all(chunk.metadata.word_count > 0 for chunk in chunks)


@pytest.mark.slow
class TestEmbeddingGeneration:
    """Tests requiring sentence-transformers model loading."""

    def test_embeddings_generated(self):
        from phantom.rag.cortex_embeddings import EmbeddingManager

        texts = [
            "Error handling in Python uses try-except blocks",
            "FastAPI supports async/await for better performance",
        ]
        manager = EmbeddingManager(model_name="all-MiniLM-L6-v2", device="cpu")
        manager.add_texts(texts)
        assert len(manager.vector_store) == len(texts)

    def test_embedding_dimension(self):
        from phantom.rag.cortex_embeddings import EmbeddingManager

        manager = EmbeddingManager(model_name="all-MiniLM-L6-v2", device="cpu")
        manager.add_texts(["test"])
        assert manager.generator.embedding_dim == 384

    def test_search_returns_results(self):
        from phantom.rag.cortex_embeddings import EmbeddingManager

        texts = [
            "Error handling in Python uses try-except blocks",
            "FastAPI supports async/await for better performance",
            "Use context managers for resource cleanup",
        ]
        manager = EmbeddingManager(model_name="all-MiniLM-L6-v2", device="cpu")
        manager.add_texts(texts)

        results = manager.search("How to handle exceptions?", top_k=3)
        assert len(results) > 0
        assert all(0 <= r.score <= 1 for r in results)

    def test_search_results_sorted_by_score(self):
        from phantom.rag.cortex_embeddings import EmbeddingManager

        texts = [
            "Error handling in Python uses try-except blocks",
            "FastAPI supports async/await for better performance",
            "Use context managers for resource cleanup",
        ]
        manager = EmbeddingManager(model_name="all-MiniLM-L6-v2", device="cpu")
        manager.add_texts(texts)

        results = manager.search("How to handle exceptions?", top_k=3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_similarity_ranking(self):
        from phantom.rag.cortex_embeddings import EmbeddingManager

        texts = [
            "Python error handling with try-except blocks",
            "Exception handling is important in Python",
            "FastAPI web framework for Python",
            "JavaScript async functions",
        ]
        manager = EmbeddingManager(model_name="all-MiniLM-L6-v2")
        manager.add_texts(texts)

        results = manager.search("How to handle errors in Python?", top_k=4)
        # Top result should be about error/exception handling
        assert "error" in results[0].text.lower() or "exception" in results[0].text.lower()

    def test_chunking_plus_embeddings_pipeline(self):
        from phantom.rag.cortex_embeddings import EmbeddingManager

        # Chunk
        chunker = MarkdownChunker(strategy=ChunkStrategy.RECURSIVE, max_tokens=150)
        chunks = chunker.chunk_text(TEST_DOCUMENT, source_file="test.md")
        assert len(chunks) > 0

        # Embed
        manager = EmbeddingManager(model_name="all-MiniLM-L6-v2")
        chunk_texts = [chunk.text for chunk in chunks]
        manager.add_texts(chunk_texts)
        assert len(manager.vector_store) == len(chunks)

        # Search
        results = manager.search("try-except syntax", top_k=2)
        assert len(results) > 0
