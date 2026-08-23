"""
Test all public imports to prevent circular dependencies and broken references.

This test suite ensures that all modules declared in __all__ can be imported
without errors. It catches issues like:
- Missing module files (e.g., phantom.providers.openai doesn't exist)
- Circular import dependencies
- Runtime import errors
"""


class TestCoreImports:
    """Test core module imports."""

    def test_phantom_main_imports(self):
        """Verify main phantom module imports work."""
        from phantom import (
            CortexProcessor,
            EmbeddingGenerator,
            SemanticChunker,
            __codename__,
            __version__,
        )

        assert __version__ == "0.1.0"
        assert __codename__ == "PHANTOM"
        assert CortexProcessor is not None
        assert SemanticChunker is not None
        assert EmbeddingGenerator is not None

    def test_core_module_imports(self):
        """Verify phantom.core module imports work."""
        from phantom.core import (
            CortexProcessor,
            DocumentInsights,
            EmbeddingGenerator,
            SemanticChunker,
        )

        assert CortexProcessor is not None
        assert SemanticChunker is not None
        assert EmbeddingGenerator is not None
        assert DocumentInsights is not None

    def test_analysis_module_imports(self):
        """Verify phantom.analysis module imports work."""
        from phantom.analysis import (
            SentimentAnalyzer,
            SentimentEngine,
            SpectreAnalyzer,
            ViabilityScorer,
        )

        assert SentimentEngine is not None
        assert SentimentAnalyzer is SentimentEngine  # Should be alias
        assert SpectreAnalyzer is not None
        assert ViabilityScorer is not None

    def test_pipeline_module_imports(self):
        """Verify phantom.pipeline module imports work."""
        from phantom.pipeline import (
            DAGPipeline,
            DataSanitizer,
            FileClassifier,
            PhantomPipeline,
        )

        assert DAGPipeline is PhantomPipeline  # Should be alias
        assert PhantomPipeline is not None
        assert FileClassifier is not None
        assert DataSanitizer is not None

    def test_providers_module_imports(self):
        """Verify phantom.providers module imports work."""
        from phantom.providers import (
            AIProvider,
            LlamaCppProvider,
            ProviderConfig,
        )

        assert AIProvider is not None
        assert ProviderConfig is not None
        assert LlamaCppProvider is not None

    def test_providers_no_broken_references(self):
        """Verify removed providers don't accidentally get imported."""
        from phantom.providers import __all__

        # These should NOT be in __all__ anymore (missing implementation)
        assert "OpenAIProvider" not in __all__
        assert "AnthropicProvider" not in __all__
        assert "DeepSeekProvider" not in __all__

        # Only these should exist
        assert "AIProvider" in __all__
        assert "ProviderConfig" in __all__
        assert "LlamaCppProvider" in __all__


class TestRAGImports:
    """Test RAG module imports."""

    def test_rag_module_basic_import(self):
        """Verify phantom.rag module can be imported."""
        import phantom.rag

        assert phantom.rag is not None

    def test_vector_store_import(self):
        """Verify vector store can be imported."""
        from phantom.rag.vectors import FAISSVectorStore

        assert FAISSVectorStore is not None


class TestAPIImports:
    """Test API module imports."""

    def test_api_module_can_import(self):
        """Verify phantom.api module exists and can be imported."""
        import phantom.api

        assert phantom.api is not None

    def test_writer_module_can_import(self):
        """Verify phantom.writer module exists and can be imported."""
        import phantom.writer

        assert phantom.writer is not None


class TestCLIImports:
    """Test CLI module imports."""

    def test_cli_module_can_import(self):
        """Verify phantom.cli module exists and can be imported."""
        import phantom.cli

        assert phantom.cli is not None


class TestCircularImports:
    """Test for circular import issues."""

    def test_no_circular_imports_on_star_import(self):
        """Verify all names in __all__ resolve without circular imports."""
        import phantom

        # Trigger lazy loading of every name declared in __all__
        for name in phantom.__all__:
            assert getattr(phantom, name) is not None, f"phantom.{name} is None"

    def test_all_submodules_can_be_imported_together(self):
        """Verify all submodules can be imported in sequence."""
        import phantom
        import phantom.analysis
        import phantom.api
        import phantom.cli
        import phantom.core
        import phantom.pipeline
        import phantom.providers
        import phantom.rag

        assert phantom is not None
        assert phantom.core is not None
        assert phantom.analysis is not None
        assert phantom.pipeline is not None
        assert phantom.providers is not None
        assert phantom.rag is not None
        assert phantom.api is not None
        assert phantom.cli is not None
