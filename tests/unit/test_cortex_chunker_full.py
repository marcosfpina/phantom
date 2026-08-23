"""
Expanded unit tests for the cortex_chunker module.

Tests: TokenCounter, RecursiveMarkdownChunker, SlidingWindowChunker,
SimpleChunker, MarkdownChunker interface.
"""

import pytest

from phantom.rag.cortex_chunker import (
    ChunkStrategy,
    MarkdownChunker,
    RecursiveMarkdownChunker,
    SimpleChunker,
    SlidingWindowChunker,
    TokenCounter,
)

pytestmark = pytest.mark.unit

SAMPLE_MD = """# Title

## Section One

This is the first section with some content about Python.

## Section Two

This is the second section with more content.

### Subsection 2.1

Details about the subsection.
"""


class TestTokenCounter:
    """Test the TokenCounter utility."""

    def test_count_nonempty(self):
        tc = TokenCounter()
        count = tc.count("Hello, world!")
        assert count > 0

    def test_count_empty(self):
        tc = TokenCounter()
        assert tc.count("") == 0

    def test_encode_returns_list(self):
        tc = TokenCounter()
        tokens = tc.encode("Hello, world!")
        assert isinstance(tokens, list)
        assert len(tokens) > 0

    def test_decode_roundtrip(self):
        tc = TokenCounter()
        text = "Hello, world!"
        tokens = tc.encode(text)
        decoded = tc.decode(tokens)
        assert decoded == text

    def test_encode_empty(self):
        tc = TokenCounter()
        assert tc.encode("") == []


class TestRecursiveMarkdownChunker:
    """Test the recursive markdown chunker."""

    def test_extract_headers(self):
        chunker = RecursiveMarkdownChunker(max_tokens=500)
        headers = chunker.extract_headers(SAMPLE_MD)
        assert len(headers) == 4  # Title, Section One, Section Two, Subsection 2.1
        # Check levels
        levels = [h[1] for h in headers]
        assert levels == [1, 2, 2, 3]

    def test_extract_headers_text(self):
        chunker = RecursiveMarkdownChunker(max_tokens=500)
        headers = chunker.extract_headers(SAMPLE_MD)
        texts = [h[2] for h in headers]
        assert "Title" in texts
        assert "Section One" in texts

    def test_split_by_headers(self):
        chunker = RecursiveMarkdownChunker(max_tokens=500)
        chunks = chunker.split_by_headers(SAMPLE_MD, "test.md")
        assert len(chunks) > 0
        assert all(c.metadata.source_file == "test.md" for c in chunks)

    def test_headers_preserved_in_metadata(self):
        chunker = RecursiveMarkdownChunker(max_tokens=500)
        chunks = chunker.split_by_headers(SAMPLE_MD, "test.md")
        # At least one chunk should have headers in metadata
        all_headers = []
        for c in chunks:
            all_headers.extend(c.metadata.headers)
        assert len(all_headers) > 0

    def test_no_headers_falls_back_to_sliding(self):
        chunker = RecursiveMarkdownChunker(max_tokens=200, overlap=20)
        text = "No headers here. Just plain text. " * 50
        chunks = chunker.chunk(text, "plain.txt")
        assert len(chunks) > 0

    def test_large_section_splitting(self):
        # Create a document where one section exceeds max_tokens
        big_section = "word " * 500
        doc = f"# Title\n\n{big_section}"
        chunker = RecursiveMarkdownChunker(max_tokens=100, overlap=20)
        chunks = chunker.chunk(doc, "big.md")
        assert len(chunks) > 1


class TestSlidingWindowChunker:
    """Test the sliding window chunker."""

    def test_produces_chunks(self):
        chunker = SlidingWindowChunker(max_tokens=50, overlap=10)
        text = "word " * 200
        chunks = chunker.chunk(text, "test.txt")
        assert len(chunks) > 1

    def test_overlap_creates_more_chunks(self):
        text = "word " * 200
        no_overlap = SlidingWindowChunker(max_tokens=50, overlap=0)
        with_overlap = SlidingWindowChunker(max_tokens=50, overlap=25)
        chunks_no = no_overlap.chunk(text, "test.txt")
        chunks_yes = with_overlap.chunk(text, "test.txt")
        # With overlap, we should get more chunks
        assert len(chunks_yes) >= len(chunks_no)

    def test_metadata_populated(self):
        # Use enough text and overlap < max_tokens to ensure chunks are produced
        chunker = SlidingWindowChunker(max_tokens=50, overlap=10)
        text = "Test content here with enough words to produce a valid chunk."
        chunks = chunker.chunk(text, "test.txt")
        assert len(chunks) > 0
        assert chunks[0].metadata.source_file == "test.txt"
        assert chunks[0].metadata.chunk_id == 0
        assert chunks[0].metadata.token_count > 0


class TestSimpleChunker:
    """Test the simple non-overlapping chunker."""

    def test_produces_chunks(self):
        chunker = SimpleChunker(max_tokens=50)
        text = "word " * 200
        chunks = chunker.chunk(text, "test.txt")
        assert len(chunks) > 1

    def test_no_overlap(self):
        chunker = SimpleChunker(max_tokens=50)
        text = "word " * 200
        chunks = chunker.chunk(text, "test.txt")
        # Each chunk should start right after the previous one ends
        for i in range(1, len(chunks)):
            assert chunks[i].metadata.start_offset == chunks[i - 1].metadata.end_offset

    def test_short_text_single_chunk(self):
        chunker = SimpleChunker(max_tokens=1000)
        chunks = chunker.chunk("Short text", "test.txt")
        assert len(chunks) == 1


class TestMarkdownChunkerInterface:
    """Test the main MarkdownChunker interface."""

    def test_strategy_selection_recursive(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.RECURSIVE)
        assert isinstance(chunker.chunker, RecursiveMarkdownChunker)

    def test_strategy_selection_sliding(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.SLIDING)
        assert isinstance(chunker.chunker, SlidingWindowChunker)

    def test_strategy_selection_simple(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.SIMPLE)
        assert isinstance(chunker.chunker, SimpleChunker)

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            MarkdownChunker(strategy="invalid")

    def test_chunk_text(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.RECURSIVE, max_tokens=200)
        chunks = chunker.chunk_text(SAMPLE_MD, source_file="test.md")
        assert len(chunks) > 0

    def test_get_stats_empty(self):
        chunker = MarkdownChunker()
        assert chunker.get_stats([]) == {}

    def test_get_stats_nonempty(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.SIMPLE, max_tokens=100)
        chunks = chunker.chunk_text("word " * 200, source_file="test.txt")
        stats = chunker.get_stats(chunks)
        assert stats["num_chunks"] == len(chunks)
        assert stats["strategy"] == "simple"
        assert stats["min_tokens"] <= stats["max_tokens"]

    def test_default_source_file(self):
        chunker = MarkdownChunker(strategy=ChunkStrategy.SIMPLE)
        chunks = chunker.chunk_text("Hello world")
        assert chunks[0].metadata.source_file == "unknown"
