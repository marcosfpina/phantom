"""
╔══════════════════════════════════════════════════════════════════╗
║  ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗ ║
║  ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║ ║
║  ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║ ║
║  ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║ ║
║  ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║ ║
║  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝ ║
╚══════════════════════════════════════════════════════════════════╝

Phantom - AI-Powered Document Intelligence & Classification Pipeline

Modules:
    core     - Insight extraction, chunking, embeddings
    analysis - Sentiment, entities, topics, viability
    pipeline - DAG execution, classification, sanitization
    providers - LLM providers (llama.cpp TURBO, OpenAI, DeepSeek, etc)
    rag      - RAG pipeline with semantic caching
    tools    - VRAM calculator, prompt workbench, auditor
    api      - FastAPI REST endpoints
    cli      - Typer CLI interface
"""

__version__ = "0.1.0"
__codename__ = "PHANTOM"

_LAZY_EXPORTS = {
    "CortexProcessor": ("phantom.core", "CortexProcessor"),
    "SemanticChunker": ("phantom.core", "SemanticChunker"),
    "EmbeddingGenerator": ("phantom.core", "EmbeddingGenerator"),
    "SentimentEngine": ("phantom.analysis", "SentimentEngine"),
    "SpectreAnalyzer": ("phantom.analysis", "SpectreAnalyzer"),
    "ViabilityScorer": ("phantom.analysis", "ViabilityScorer"),
    "DAGPipeline": ("phantom.pipeline", "DAGPipeline"),
    "PhantomPipeline": ("phantom.pipeline", "PhantomPipeline"),
    "FileClassifier": ("phantom.pipeline", "FileClassifier"),
    "DataSanitizer": ("phantom.pipeline", "DataSanitizer"),
}


def __getattr__(name):
    """Resolve public exports lazily to keep lightweight imports cheap."""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value

__all__ = [
    # Version info
    "__version__",
    "__codename__",
    # Core
    "CortexProcessor",
    "SemanticChunker",
    "EmbeddingGenerator",
    # Analysis
    "SentimentEngine",
    "SpectreAnalyzer",
    "ViabilityScorer",
    # Pipeline
    "DAGPipeline",
    "PhantomPipeline",
    "FileClassifier",
    "DataSanitizer",
]
