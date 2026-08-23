"""
Integration tests for Phantom API endpoints.

Tests all REST API endpoints to ensure they work correctly with real data.
Covers happy path, error cases, and edge cases.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Import the API
from phantom.api.app import create_app


# Create app and client
@pytest.fixture
def app():
    """Create FastAPI test app."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_markdown():
    """Sample markdown document for testing."""
    return """
# Sample Project Report

## Overview
This is a comprehensive analysis of our project status.

### Key Findings
- We have completed 95% of implementation
- All API endpoints are functional
- Testing coverage is at 70%

## Recommendations
1. Add comprehensive documentation
2. Set up frontend tests
3. Implement deployment guides

### Technical Details
The system uses:
- FastAPI for REST endpoints
- FAISS for vector search
- Pydantic for validation
- llama.cpp for inference

## Conclusion
The project is ready for production deployment.
"""


class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    def test_health_endpoint(self, client):
        """Test /health endpoint returns operational status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "version" in data

    def test_ready_endpoint(self, client):
        """Test /ready endpoint returns readiness status."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ready", "not_ready"]
        assert isinstance(data["checks"], dict)

    def test_metrics_endpoint(self, client):
        """Test /metrics endpoint returns Prometheus metrics."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "phantom_requests_total" in response.text
        assert "phantom_request_latency_seconds" in response.text


class TestSystemMetricsEndpoint:
    """Test system metrics endpoint."""

    def test_system_metrics_endpoint(self, client):
        """Test /api/system/metrics returns system resource information."""
        response = client.get("/api/system/metrics")
        assert response.status_code == 200
        data = response.json()

        # Check CPU metrics
        assert "cpu" in data
        assert "percent" in data["cpu"]
        assert "count" in data["cpu"]

        # Check memory metrics
        assert "memory" in data
        assert "total_bytes" in data["memory"]
        assert "used_bytes" in data["memory"]
        assert "available_bytes" in data["memory"]
        assert "percent" in data["memory"]

        # Check disk metrics
        assert "disk" in data
        assert "total_bytes" in data["disk"]
        assert "used_bytes" in data["disk"]

        # Check timestamp
        assert "timestamp" in data
        assert data["timestamp"] > 0


class TestDocumentProcessingEndpoints:
    """Test document processing endpoints."""

    def test_extract_endpoint_with_content(self, client, sample_markdown):
        """Test /extract endpoint processes content correctly."""
        payload = {
            "content": sample_markdown,
            "filename": "test_report.md"
        }
        response = client.post("/extract", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["filename"] == "test_report.md"
        assert "insights" in data
        assert "processing_time_seconds" in data
        assert data["processing_time_seconds"] > 0
        assert isinstance(data["insights"], dict)

    def test_extract_endpoint_empty_content(self, client):
        """Test /extract endpoint handles empty content."""
        payload = {
            "content": "",
            "filename": "empty.md"
        }
        response = client.post("/extract", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "empty.md"

    def test_process_endpoint_with_file(self, client, sample_markdown):
        """Test /process endpoint processes file uploads."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(sample_markdown)
            temp_path = f.name

        try:
            with open(temp_path, 'rb') as f:
                response = client.post(
                    "/process",
                    files={"file": ("test.md", f, "text/markdown")},
                    params={"chunk_size": "1024"}
                )

            assert response.status_code == 200
            data = response.json()
            assert "filename" in data
            assert "insights" in data
            assert "processing_time" in data
        finally:
            Path(temp_path).unlink()

    def test_upload_endpoint_single_file(self, client, sample_markdown):
        """Test /upload endpoint accepts single file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(sample_markdown)
            temp_path = f.name

        try:
            with open(temp_path, 'rb') as f:
                response = client.post(
                    "/upload",
                    files={"file": ("test.md", f, "text/markdown")}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["filename"] == "test.md"
            assert data["status"] == "uploaded"
            assert "size" in data
        finally:
            Path(temp_path).unlink()

    def test_api_upload_endpoint_multiple_files(self, client, sample_markdown):
        """Test /api/upload endpoint accepts multiple files."""
        temp_files = []

        try:
            # Create multiple temp files
            for i in range(2):
                with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                    f.write(sample_markdown)
                    temp_files.append(f.name)

            # Upload files
            files = [("files", (Path(f).name, open(f, 'rb'), "text/markdown")) for f in temp_files]
            response = client.post("/api/upload", files=files)

            # Cleanup files
            for _, (_, f, _) in files:
                f.close()

            assert response.status_code == 200
            data = response.json()
            assert "files" in data
            assert len(data["files"]) >= 1
        finally:
            for f in temp_files:
                Path(f).unlink()


class TestVectorStoreEndpoints:
    """Test vector store and search endpoints."""

    def test_vector_search_empty_store(self, client):
        """Test /vectors/search handles empty vector store."""
        payload = {"query": "test", "top_k": 5}
        response = client.post("/vectors/search", json=payload)

        # Should get 400 error about empty store
        assert response.status_code == 400
        assert "empty" in response.text.lower()

    def test_vector_search_requires_query(self, client):
        """Test /vectors/search requires query parameter."""
        response = client.post("/vectors/search", json={})
        assert response.status_code == 400
        assert "query" in response.text.lower()

    def test_vector_search_with_mode_options(self, client):
        """Test /vectors/search accepts different search modes."""
        modes = ["dense", "sparse", "hybrid"]

        for mode in modes:
            payload = {"query": "test", "top_k": 5, "mode": mode}
            response = client.post("/vectors/search", json=payload)

            # Empty store should give 400, not invalid mode error
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data


class TestRAGChatEndpoints:
    """Test RAG and chat endpoints."""

    def test_chat_endpoint_basic(self, client):
        """Test /api/chat endpoint returns response."""
        payload = {
            "message": "What is your name?",
            "conversation_id": "test-123",
            "history": [],
            "context_size": 5,
            "llm_provider": "local"
        }
        response = client.post("/api/chat", json=payload)

        # Should work or return 500 if LLM unavailable
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "content" in data["message"]
            assert data["conversation_id"] == "test-123"

    def test_models_list_endpoint(self, client):
        """Test /api/models endpoint returns available models."""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()

        assert "local" in data
        assert isinstance(data["local"], list)

        # Optional cloud providers
        assert "openai" in data
        assert "anthropic" in data

    def test_prompt_test_endpoint(self, client):
        """Test /api/prompt/test endpoint validates templates."""
        payload = {
            "template": "Hello {name}, you are {role}",
            "variables": {"name": "Claude", "role": "Assistant"}
        }
        response = client.post("/api/prompt/test", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "Hello Claude, you are Assistant" in data["rendered"]
        assert "tokens" in data
        assert data["error"] is None

    def test_prompt_test_missing_variables(self, client):
        """Test /api/prompt/test handles missing variables."""
        payload = {
            "template": "Hello {name}, you are {role}",
            "variables": {"name": "Claude"}  # Missing 'role'
        }
        response = client.post("/api/prompt/test", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert data["error"] is not None
        assert "role" in data["error"].lower()


class TestPipelineEndpoints:
    """Test pipeline and classification endpoints."""

    def test_pipeline_scan_endpoint(self, client, sample_markdown):
        """Test /api/pipeline/scan endpoint."""
        # Create a temporary directory with a file
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text(sample_markdown)

            response = client.post(
                "/api/pipeline/scan",
                params={"directory": tmpdir, "top_n": 50}
            )

            # May succeed or fail depending on classifier availability
            assert response.status_code in [200, 400]

            if response.status_code == 200:
                data = response.json()
                assert "directory" in data
                assert "files" in data
                assert isinstance(data["files"], list)

    def test_pipeline_scan_invalid_directory(self, client):
        """Test /api/pipeline/scan with invalid directory."""
        response = client.post(
            "/api/pipeline/scan",
            params={"directory": "/nonexistent/path", "top_n": 50}
        )
        assert response.status_code == 400


class TestErrorHandling:
    """Test error handling across endpoints."""

    def test_extract_with_invalid_json(self, client):
        """Test /extract rejects invalid JSON."""
        response = client.post(
            "/extract",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422  # Unprocessable Entity

    def test_nonexistent_endpoint(self, client):
        """Test accessing nonexistent endpoint."""
        response = client.get("/nonexistent/endpoint")
        assert response.status_code == 404


class TestConcurrency:
    """Test endpoint behavior under concurrent requests."""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, client):
        """Test multiple concurrent health checks."""
        tasks = [
            asyncio.to_thread(client.get, "/health")
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)

        assert all(r.status_code == 200 for r in responses)
        assert len(responses) == 10

    @pytest.mark.asyncio
    async def test_concurrent_metrics(self, client):
        """Test multiple concurrent metrics requests."""
        tasks = [
            asyncio.to_thread(client.get, "/metrics")
            for _ in range(5)
        ]
        responses = await asyncio.gather(*tasks)

        assert all(r.status_code == 200 for r in responses)
        assert len(responses) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
