"""
Unit tests for the latency optimizer module.

Tests: QueryCache, BatchProcessor, LatencyMetrics, LatencyOptimizer.
"""

import time
from unittest.mock import MagicMock

import pytest

from phantom.analysis.latency_optimizer import (
    BatchProcessor,
    LatencyMetrics,
    LatencyOptimizer,
    QueryCache,
)

pytestmark = pytest.mark.unit


class TestQueryCache:
    """Test LRU cache for semantic search queries."""

    def test_set_and_get(self):
        cache = QueryCache(maxsize=10, ttl_seconds=60)
        cache.set("hello", 5, ["result1"])
        assert cache.get("hello", 5) == ["result1"]

    def test_get_missing_returns_none(self):
        cache = QueryCache()
        assert cache.get("nonexistent", 5) is None

    def test_ttl_expiration(self):
        cache = QueryCache(maxsize=10, ttl_seconds=0)
        cache.set("query", 5, "result")
        # TTL=0 means immediate expiry
        time.sleep(0.01)
        assert cache.get("query", 5) is None

    def test_lru_eviction(self):
        cache = QueryCache(maxsize=2, ttl_seconds=3600)
        cache.set("q1", 5, "r1")
        time.sleep(0.01)  # Ensure different timestamps
        cache.set("q2", 5, "r2")
        # Cache is full, adding a third should evict the oldest (q1)
        cache.set("q3", 5, "r3")
        assert cache.get("q1", 5) is None
        assert cache.get("q2", 5) == "r2"
        assert cache.get("q3", 5) == "r3"

    def test_cache_key_differs_by_top_k(self):
        cache = QueryCache()
        cache.set("query", 5, "r5")
        cache.set("query", 10, "r10")
        assert cache.get("query", 5) == "r5"
        assert cache.get("query", 10) == "r10"

    def test_clear(self):
        cache = QueryCache()
        cache.set("a", 1, "x")
        cache.set("b", 2, "y")
        cache.clear()
        assert cache.get("a", 1) is None
        assert cache.get("b", 2) is None

    def test_stats(self):
        cache = QueryCache(maxsize=100, ttl_seconds=3600)
        cache.set("a", 1, "x")
        cache.set("b", 2, "y")
        stats = cache.stats()
        assert stats["size"] == 2
        assert stats["maxsize"] == 100
        assert stats["ttl_seconds"] == 3600


class TestBatchProcessor:
    """Test batch processing queue."""

    def test_add_below_batch_size_returns_none(self):
        bp = BatchProcessor(batch_size=3)
        assert bp.add("item1") is None
        assert bp.add("item2") is None

    def test_add_at_batch_size_returns_batch(self):
        bp = BatchProcessor(batch_size=2)
        bp.add("item1")
        result = bp.add("item2")
        assert result == ["item1", "item2"]

    def test_flush_returns_queued_items(self):
        bp = BatchProcessor(batch_size=10)
        bp.add("a")
        bp.add("b")
        batch = bp.flush()
        assert batch == ["a", "b"]

    def test_flush_clears_queue(self):
        bp = BatchProcessor(batch_size=10)
        bp.add("a")
        bp.flush()
        assert bp.flush() == []

    def test_auto_flush_resets_queue(self):
        bp = BatchProcessor(batch_size=2)
        bp.add("x")
        bp.add("y")  # triggers auto-flush
        assert len(bp.queue) == 0


class TestLatencyMetrics:
    """Test latency metrics tracking."""

    def test_record_and_get_stats(self):
        m = LatencyMetrics()
        m.record("search", 10.0)
        m.record("search", 20.0)
        m.record("search", 30.0)
        stats = m.get_stats()
        assert stats["count"] == 3
        assert stats["avg_ms"] == 20.0
        assert stats["min_ms"] == 10.0
        assert stats["max_ms"] == 30.0

    def test_get_stats_empty(self):
        m = LatencyMetrics()
        stats = m.get_stats()
        assert stats == {"count": 0}

    def test_get_stats_by_type(self):
        m = LatencyMetrics()
        m.record("search", 10.0)
        m.record("embed", 50.0)
        m.record("search", 20.0)
        stats = m.get_stats("search")
        assert stats["count"] == 2
        assert stats["avg_ms"] == 15.0

    def test_percentile_p50(self):
        m = LatencyMetrics()
        for v in [10, 20, 30, 40, 50]:
            m.record("search", float(v))
        stats = m.get_stats()
        assert stats["p50_ms"] == 30.0

    def test_history_truncation(self):
        m = LatencyMetrics()
        m.max_history = 5
        for i in range(10):
            m.record("search", float(i))
        assert len(m.queries) == 5
        # Should keep the last 5
        assert m.queries[0]["latency_ms"] == 5.0


class TestLatencyOptimizer:
    """Test the optimizer facade."""

    def test_cached_search_miss_then_hit(self):
        optimizer = LatencyOptimizer()
        search_fn = MagicMock(return_value=["result1"])

        # First call: cache miss, calls search_fn
        r1 = optimizer.cached_search("hello", 5, search_fn)
        assert r1 == ["result1"]
        search_fn.assert_called_once_with("hello", 5)

        # Second call: cache hit, does NOT call search_fn again
        r2 = optimizer.cached_search("hello", 5, search_fn)
        assert r2 == ["result1"]
        assert search_fn.call_count == 1

    def test_stats_structure(self):
        optimizer = LatencyOptimizer()
        stats = optimizer.stats()
        assert "cache" in stats
        assert "metrics" in stats
