"""
Shared fixtures for the Phantom test suite.

Usage:
    Fixtures here are available to all tests automatically.
    No import required — pytest discovers them via conftest.py.
"""

import numpy as np
import pytest

# ── Vector / Embedding fixtures ─────────────────────────────────────

EMBEDDING_DIM = 4  # Small dim for fast unit tests


@pytest.fixture
def dummy_embeddings():
    """Two orthogonal 4-dim embeddings with labels."""
    e1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    e2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    return np.vstack([e1, e2]), ["doc_alpha", "doc_beta"]


@pytest.fixture
def query_near_first():
    """Query vector close to the first embedding."""
    return np.array([0.95, 0.05, 0.0, 0.0], dtype=np.float32)


@pytest.fixture
def query_near_second():
    """Query vector close to the second embedding."""
    return np.array([0.05, 0.95, 0.0, 0.0], dtype=np.float32)


# ── NLP / Analysis fixtures ─────────────────────────────────────────

@pytest.fixture
def sentiment_engine():
    """SentimentEngine instance (VADER, no spaCy dependency)."""
    from phantom.analysis.sentiment_analysis import SentimentEngine

    return SentimentEngine(use_spacy=False)


# ── Sample text payloads ────────────────────────────────────────────

SAMPLE_MARKDOWN = """
# Project Alpha

## Overview
This project delivers a scalable document processing pipeline.

## Goals
- Reduce latency by 40%
- Improve accuracy to 95%

## Risks
- Vendor lock-in with cloud provider
- Team capacity constraints
"""


@pytest.fixture
def sample_markdown():
    return SAMPLE_MARKDOWN


@pytest.fixture
def sample_texts():
    return [
        "I love this product, it is amazing!",
        "This is a terrible mistake and I hate it.",
        "The box is made of cardboard.",
        "The weather is nice today.",
        "This service completely failed to deliver.",
    ]
