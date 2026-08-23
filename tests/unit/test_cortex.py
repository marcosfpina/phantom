"""
Unit tests for the CORTEX core module.

Tests: imports, Pydantic models, PromptBuilder, JSON parsing, SystemMonitor.
"""

import pytest

from phantom.core import cortex

pytestmark = pytest.mark.unit


class TestImports:
    """Verify that all required dependencies are importable."""

    def test_core_library_imports(self):
        import psutil  # noqa: F401
        import requests  # noqa: F401
        from pydantic import BaseModel, Field, ValidationError  # noqa: F401
        from rich.console import Console  # noqa: F401
        from rich.progress import Progress  # noqa: F401

    def test_cortex_module_imports(self):
        assert hasattr(cortex, "CortexProcessor")
        assert hasattr(cortex, "PromptBuilder")
        assert hasattr(cortex, "SystemMonitor")


class TestPydanticModels:
    """Test Pydantic model construction and validation."""

    def test_theme_model(self):
        theme = cortex.Theme(
            title="Test Theme",
            description="A test theme description",
            confidence=cortex.ExtractionLevel.HIGH,
            keywords=["test", "validation"],
        )
        assert theme.title == "Test Theme"
        assert theme.confidence == cortex.ExtractionLevel.HIGH
        assert "test" in theme.keywords

    def test_pattern_model(self):
        pattern = cortex.Pattern(
            pattern_type="test",
            description="Test pattern",
            examples=["example1", "example2"],
            frequency=2,
        )
        assert pattern.pattern_type == "test"
        assert pattern.frequency == 2
        assert len(pattern.examples) == 2

    def test_learning_model(self):
        learning = cortex.Learning(
            title="Test Learning",
            description="Test learning description",
            category="technical",
            actionable=True,
        )
        assert learning.title == "Test Learning"
        assert learning.actionable is True

    def test_concept_model(self):
        concept = cortex.Concept(
            name="Test Concept",
            definition="Test definition",
            related_concepts=["concept1"],
            complexity=cortex.ExtractionLevel.MEDIUM,
        )
        assert concept.name == "Test Concept"
        assert concept.complexity == cortex.ExtractionLevel.MEDIUM

    def test_recommendation_model(self):
        rec = cortex.Recommendation(
            title="Test Recommendation",
            description="Test recommendation description",
            priority=cortex.ExtractionLevel.HIGH,
            category="best_practice",
            implementation_effort="low",
        )
        assert rec.title == "Test Recommendation"
        assert rec.priority == cortex.ExtractionLevel.HIGH
        assert rec.category == "best_practice"


class TestPromptBuilder:
    """Test prompt building and JSON parsing."""

    def test_build_extraction_prompt_contains_content(self):
        content = "# Test Document\n\nThis is a test markdown file."
        prompt = cortex.PromptBuilder.build_extraction_prompt(content, "test.md")
        assert "Test Document" in prompt

    def test_build_extraction_prompt_contains_filename(self):
        content = "# Test Document\n\nSome content."
        prompt = cortex.PromptBuilder.build_extraction_prompt(content, "test.md")
        assert "test.md" in prompt

    def test_build_extraction_prompt_requests_json(self):
        content = "# Test"
        prompt = cortex.PromptBuilder.build_extraction_prompt(content, "test.md")
        assert "JSON" in prompt

    def test_parse_json_from_markdown_code_block(self):
        response = """```json
{
  "themes": [],
  "patterns": [],
  "learnings": [],
  "concepts": [],
  "recommendations": []
}
```"""
        data = cortex.PromptBuilder.parse_json_response(response)
        assert data is not None
        assert "themes" in data
        assert isinstance(data["themes"], list)

    def test_parse_json_plain(self):
        response = """
{
  "themes": [{"title": "Test", "description": "Test desc", "confidence": "high", "keywords": []}],
  "patterns": [],
  "learnings": [],
  "concepts": [],
  "recommendations": []
}
"""
        data = cortex.PromptBuilder.parse_json_response(response)
        assert data is not None
        assert len(data["themes"]) == 1
        assert data["themes"][0]["title"] == "Test"


class TestSemanticChunker:
    """Test SemanticChunker text splitting."""

    def test_chunk_short_text(self):
        chunker = cortex.SemanticChunker(max_tokens=1024, overlap=128)
        chunks = chunker.chunk_text("Hello world", "test.md")
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world"
        assert chunks[0].source_file == "test.md"

    def test_chunk_text_multiple_chunks(self):
        chunker = cortex.SemanticChunker(max_tokens=50, overlap=5)
        # Create text that needs multiple chunks (small for speed)
        text = "\n\n".join([f"## Section {i}\n\nContent for section {i} with words." for i in range(5)])
        chunks = chunker.chunk_text(text, "test.md")
        assert len(chunks) > 1

    def test_chunk_ids_sequential(self):
        chunker = cortex.SemanticChunker(max_tokens=50, overlap=5)
        text = "\n\n".join([f"## Section {i}\n\nSome content here with words." for i in range(5)])
        chunks = chunker.chunk_text(text, "test.md")
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id == i

    def test_count_tokens(self):
        chunker = cortex.SemanticChunker(max_tokens=100)
        count = chunker.count_tokens("Hello world, this is a test.")
        assert count > 0
        assert isinstance(count, int)

    def test_chunk_file(self, tmp_path):
        test_file = tmp_path / "test.md"
        test_file.write_text("# Title\n\nSome content here.")
        chunker = cortex.SemanticChunker(max_tokens=1024)
        chunks = chunker.chunk_file(test_file)
        assert len(chunks) >= 1
        assert chunks[0].source_file == "test.md"

    def test_chunk_preserves_content(self):
        chunker = cortex.SemanticChunker(max_tokens=1024)
        text = "This is test content that should be preserved."
        chunks = chunker.chunk_text(text, "file.md")
        assert text in chunks[0].text

    def test_chunk_empty_text(self):
        chunker = cortex.SemanticChunker(max_tokens=1024)
        chunks = chunker.chunk_text("", "empty.md")
        assert len(chunks) == 0 or chunks[0].text.strip() == ""


class TestExtractionLevel:
    """Test ExtractionLevel enum."""

    def test_values_exist(self):
        assert cortex.ExtractionLevel.HIGH is not None
        assert cortex.ExtractionLevel.MEDIUM is not None
        assert cortex.ExtractionLevel.LOW is not None


class TestDocumentInsights:
    """Test DocumentInsights Pydantic model."""

    def test_empty_insights(self):
        insights = cortex.DocumentInsights(
            file_path="/tmp/test.md",
            file_name="test.md",
            processed_at="2026-02-14T00:00:00",
            word_count=0,
            processing_time_seconds=0.0,
        )
        assert insights.themes == []
        assert insights.patterns == []
        assert insights.learnings == []
        assert insights.concepts == []
        assert insights.recommendations == []

    def test_insights_with_data(self):
        theme = cortex.Theme(
            title="Test", description="desc",
            confidence=cortex.ExtractionLevel.HIGH, keywords=["k1"],
        )
        insights = cortex.DocumentInsights(
            file_path="/tmp/test.md",
            file_name="test.md",
            processed_at="2026-02-14T00:00:00",
            word_count=100,
            processing_time_seconds=1.5,
            themes=[theme],
        )
        assert len(insights.themes) == 1
        dumped = insights.model_dump()
        assert "themes" in dumped
        assert len(dumped["themes"]) == 1


class TestSystemMonitor:
    """Test system resource monitoring."""

    def test_ram_usage_keys(self):
        from rich.console import Console

        monitor = cortex.SystemMonitor(Console())
        ram = monitor.get_ram_usage()
        assert "used_mb" in ram
        assert "free_mb" in ram
        assert "total_mb" in ram
        assert "usage_percent" in ram

    def test_ram_usage_values_in_range(self):
        from rich.console import Console

        monitor = cortex.SystemMonitor(Console())
        ram = monitor.get_ram_usage()
        assert 0 <= ram["usage_percent"] <= 100
        assert ram["total_mb"] > 0

    def test_vram_usage_returns_dict(self):
        from rich.console import Console

        monitor = cortex.SystemMonitor(Console())
        vram = monitor.get_vram_usage()
        assert isinstance(vram, dict)
        # GPU may or may not be available; just check it doesn't crash
