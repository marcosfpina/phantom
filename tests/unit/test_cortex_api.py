from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from phantom.api import cortex_api
from phantom.api.cortex_api import app

client = TestClient(app)


def test_llm_endpoints_have_distinct_defaults():
    assert cortex_api.LLAMACPP_URL == "http://localhost:8080"
    assert cortex_api.SECURELLM_BRIDGE_URL == "http://localhost:8081"
    assert cortex_api.LLAMACPP_URL != cortex_api.SECURELLM_BRIDGE_URL


def test_direct_local_call_uses_llamacpp_url(monkeypatch):
    response = MagicMock(ok=True)
    response.json.return_value = {"choices": [{"message": {"content": "local response"}}]}
    monkeypatch.setattr(cortex_api, "LLAMACPP_URL", "http://llama.test:9000")

    with patch("requests.post", return_value=response) as post:
        content = cortex_api._call_direct(
            "local",
            None,
            [{"role": "user", "content": "Hello"}],
            temperature=0.2,
            max_tokens=32,
        )

    assert content == "local response"
    assert post.call_args.args[0] == ("http://llama.test:9000/v1/chat/completions")


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "operational"


@patch("phantom.api.cortex_api.MarkdownProcessor")
def test_process_endpoint(mock_processor):
    # Mock the processor instance and its method
    instance = mock_processor.return_value

    # Mock the insights object returned by process_single_file
    mock_insights = MagicMock()
    mock_insights.dict.return_value = {
        "themes": [{"title": "Test Theme", "description": "Test Desc", "confidence": "high"}],
        "file_name": "test.md",
    }
    mock_insights.processing_time_seconds = 0.5

    instance.process_single_file.return_value = mock_insights

    # Create a dummy file
    files = {"file": ("test.md", b"# Test content", "text/markdown")}

    response = client.post("/process", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.md"
    assert "insights" in data
    instance.process_single_file.assert_called_once()


@patch("phantom.api.cortex_api.SpectreAnalyzer")
def test_analyze_endpoint(mock_analyzer):
    # Mock analyzer
    instance = mock_analyzer.return_value

    mock_analysis = MagicMock()
    # Mock nested sentiment object
    mock_sentiment = MagicMock()
    mock_sentiment.to_dict.return_value = {"compound": 0.8, "label": "positive"}
    mock_analysis.sentiment = mock_sentiment

    mock_analysis.entities = []
    mock_analysis.topics = []

    instance.analyze_document.return_value = mock_analysis

    files = {"file": ("test.md", b"I love crypto", "text/markdown")}
    response = client.post("/analyze", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.md"
    assert "sentiment" in data
