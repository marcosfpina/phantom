#!/usr/bin/env python3
"""
CORTEX API - FastAPI Backend for Cortex Desktop
Exposes Cortex and Spectre engines via HTTP endpoints.
"""

import logging
import os
import shutil
import sys
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import Core Engines
try:
    from phantom.analysis.spectre import DocumentAnalysis, SpectreAnalyzer
    from phantom.core.cortex import CortexProcessor as MarkdownProcessor
    from phantom.core.cortex import DocumentInsights as MarkdownInsights
except ImportError as e:
    print(f"CRITICAL: Failed to import core engines: {e}")
    sys.exit(1)

# Configuration
TEMP_DIR = Path(".phantom/staging")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# SecureLLM Bridge (M3.4) — all LLM calls route through the bridge in production.
# Set SECURELLM_BRIDGE_URL to the bridge address; empty string disables routing
# so direct provider calls are used (local dev without the bridge running).
SECURELLM_BRIDGE_URL = os.environ.get(
    "SECURELLM_BRIDGE_URL", "http://localhost:8081"
).rstrip("/")

# ml-ops-api (M7.4) — local GPU inference via candle/Rust. Tried before the cloud
# bridge so requests stay on-prem when GPU is available.
# Set ML_OPS_ENABLED=true to activate. Defaults to disabled so local dev without
# a GPU still works.
ML_OPS_ENABLED = os.environ.get("ML_OPS_ENABLED", "false").lower() == "true"
ML_OPS_API_URL = os.environ.get("ML_OPS_API_URL", "http://localhost:8083").rstrip("/")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cortex_api")

# App Definition
app = FastAPI(
    title="Cortex API",
    description="Backend API for Cortex Desktop (Tauri integration)",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════


class ProcessResponse(BaseModel):
    filename: str
    insights: dict[str, Any]
    processing_time: float


class AnalyzeResponse(BaseModel):
    filename: str
    sentiment: dict[str, Any]
    entities: list[dict[str, Any]]
    topics: list[dict[str, Any]]


# ═══════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════


def save_upload_file(upload_file: UploadFile) -> Path:
    try:
        filename = upload_file.filename or "upload"
        suffix = Path(filename).suffix
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix, dir=TEMP_DIR
        ) as tmp:
            shutil.copyfileobj(upload_file.file, tmp)
            tmp_path = Path(tmp.name)
        return tmp_path
    finally:
        upload_file.file.close()


def cleanup_file(path: Path) -> None:
    if path.exists():
        try:
            os.remove(path)
        except Exception as e:
            logger.error(f"Failed to delete temp file {path}: {e}")


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@app.get("/health")
async def health_check():
    return {
        "status": "operational",
        "version": "1.0.0",
        "engines": {"cortex": "loaded", "spectre": "loaded"},
    }


@app.post("/process", response_model=ProcessResponse)
async def process_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    chunk_strategy: str | None = Query(
        None, description="Chunking strategy: recursive, sliding, simple"
    ),
    chunk_size: int = 1024,
):
    """
    Process a document using CORTEX (LLM Extraction).
    """
    logger.info(f"Processing upload: {file.filename}")

    tmp_path = save_upload_file(file)
    background_tasks.add_task(cleanup_file, tmp_path)

    try:
        # Initialize Processor
        # Note: In a real app, we might want to reuse the processor or use a queue
        # For now, we instantiate per request but point to a dummy output file
        dummy_output = TEMP_DIR / f"{uuid.uuid4()}.jsonl"

        processor = MarkdownProcessor(
            input_dir=str(
                TEMP_DIR
            ),  # Dummy, not used for single file logic refactor might be needed
            output_file=str(dummy_output),
            chunking_strategy=chunk_strategy,
            chunk_size=chunk_size,
            verbose=False,
        )

        # We need to hack/refactor MarkdownProcessor slightly or use internal method
        # The current CORTEX implementation scans a directory.
        # Let's call the internal method directly.

        insights = processor.process_single_file(tmp_path)

        if not insights:
            raise HTTPException(status_code=500, detail="Failed to extract insights")

        # Clean up the dummy output if created
        if dummy_output.exists():
            os.remove(dummy_output)

        return ProcessResponse(
            filename=file.filename,
            insights=insights.dict(),
            processing_time=insights.processing_time_seconds,
        )

    except Exception as e:
        logger.error(f"Error processing {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
):
    """
    Analyze a document using SPECTRE (Sentiment & Entities).
    """
    logger.info(f"Analyzing upload: {file.filename}")

    tmp_path = save_upload_file(file)
    background_tasks.add_task(cleanup_file, tmp_path)

    try:
        analyzer = SpectreAnalyzer()
        analysis = analyzer.analyze_document(tmp_path)

        if not analysis:
            raise HTTPException(status_code=500, detail="Analysis failed")

        return AnalyzeResponse(
            filename=file.filename,
            sentiment=analysis.sentiment.to_dict() if analysis.sentiment else {},
            entities=[asdict(e) for e in analysis.entities],
            topics=[asdict(t) for t in analysis.topics],
        )

    except Exception as e:
        logger.error(f"Error analyzing {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# JUDGE ENDPOINT (AI-OS-Agent Integration)
# ═══════════════════════════════════════════════════════════════

from phantom.api.judge_api import (
    PhantomGateBundle,
    PhantomGateResponse,
    get_judgment_engine,
)


@app.post("/judge", response_model=PhantomGateResponse)
async def judge_bundle(bundle: PhantomGateBundle):
    """
    Julgar bundle de métricas do AI-OS-Agent

    Recebe:
    - Métricas do sistema (CPU, RAM, thermal, disk, network)
    - Alertas detectados
    - Logs recentes (journald)

    Retorna:
    - Severidade geral (info/warning/critical)
    - Insights sobre o estado do sistema
    - ADRs relevantes consultadas
    - Recomendações de ações
    """
    logger.info(
        f"Received bundle from {bundle.hostname}: "
        f"{len(bundle.alerts)} alerts, {len(bundle.logs)} logs"
    )

    try:
        engine = get_judgment_engine()
        result = engine.judge(bundle)

        logger.info(
            f"Judgment complete: severity={result.severity}, "
            f"insights={len(result.insights)}, "
            f"adrs={len(result.relevant_adrs)}"
        )

        return result

    except Exception as e:
        logger.error(f"Error judging bundle: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════
# LLM / CHAT ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: str
    history: list[ChatMessage] = []
    context_size: int = 5
    llm_provider: str = "tensor_forge"
    model: str = "local-llamacpp"
    temperature: float = 0.7
    max_tokens: int = 1024

class ChatResponse(BaseModel):
    message: dict[str, Any]
    conversation_id: str

@app.get("/api/validate")
async def validate_providers():
    """Diagnose connectivity to each LLM provider endpoint."""
    import requests as _req
    results = {}

    # Test llamacpp on :8081
    try:
        r = _req.get("http://localhost:8081/health", timeout=3)
        results["tensor_forge"] = {"ok": r.ok, "status": r.status_code, "detail": r.text[:200]}
    except Exception:
        # Try /v1/models as fallback probe
        try:
            r = _req.get("http://localhost:8081/v1/models", timeout=3)
            results["tensor_forge"] = {"ok": r.ok, "status": r.status_code, "detail": r.text[:200]}
        except Exception as e2:
            results["tensor_forge"] = {"ok": False, "status": None, "detail": str(e2)}

    results["openai"] = {"ok": bool(os.environ.get("OPENAI_API_KEY")), "detail": "key present" if os.environ.get("OPENAI_API_KEY") else "OPENAI_API_KEY not set"}
    results["anthropic"] = {"ok": bool(os.environ.get("ANTHROPIC_API_KEY")), "detail": "key present" if os.environ.get("ANTHROPIC_API_KEY") else "ANTHROPIC_API_KEY not set"}

    return results


@app.get("/api/models")
async def list_models():
    """List available models per provider."""
    return {
        "tensor_forge": [
            {"id": "local-llamacpp", "name": "Local LLaMA.cpp (8081)"},
            {"id": "qwen3-vl-8b", "name": "Qwen 3 VL"},
        ],
        "openai": [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
        ],
        "anthropic": [
            {"id": "claude-3-opus", "name": "Claude 3 Opus"},
            {"id": "claude-3-sonnet", "name": "Claude 3 Sonnet"},
        ],
    }

def _bridge_model_id(provider: str, model: str | None) -> str:
    """Map cortex provider names to securellm-bridge {provider}/{model} identifiers."""
    if provider in ("tensor_forge", "local"):
        # Local llamacpp — bridge routes to configured local endpoint.
        # Do not send model name (llamacpp uses whatever is loaded at startup).
        return "local/llamacpp"
    if provider == "openai":
        return f"openai/{model}" if model else "openai/gpt-4o"
    if provider == "anthropic":
        return f"anthropic/{model}" if model else "anthropic/claude-3-sonnet"
    if provider == "deepseek":
        return f"deepseek/{model}" if model else "deepseek/deepseek-chat"
    return f"{provider}/{model}" if model else provider


def _call_via_bridge(provider: str, model: str | None, messages: list, temperature: float, max_tokens: int) -> str:
    """
    Route an LLM request through securellm-bridge.

    The bridge exposes an OpenAI-compatible /v1/chat/completions endpoint and
    handles provider-specific normalisation (Anthropic schema, auth headers, etc.)
    internally. All requests use a unified JSON payload format.

    Returns the assistant message content string.
    Raises requests.exceptions.ConnectionError if the bridge is unreachable.
    """
    import requests as _requests

    bridge_model = _bridge_model_id(provider, model)
    payload: dict = {
        "model": bridge_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # Local llamacpp: bridge may expect no model field for pass-through
    if provider in ("tensor_forge", "local"):
        payload.pop("model", None)

    res = _requests.post(
        f"{SECURELLM_BRIDGE_URL}/v1/chat/completions",
        json=payload,
        timeout=120,
    )
    if not res.ok:
        raise Exception(f"SecureLLM Bridge error ({res.status_code}): {res.text[:200]}")
    return res.json().get("choices", [{}])[0].get("message", {}).get("content", "")


def _call_via_ml_ops(model: str | None, messages: list, temperature: float, max_tokens: int) -> str:
    """
    Route an LLM request to ml-ops-api (local GPU inference via candle).

    ml-ops-api speaks the OpenAI /v1/chat/completions protocol. It runs a candle
    Rust inference engine and falls back to llama.cpp if candle is unavailable.

    Raises requests.exceptions.ConnectionError if ml-ops-api is unreachable.
    Raises Exception on any API error.
    """
    import requests as _requests

    payload: dict = {
        "model": model or "local-model",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    res = _requests.post(
        f"{ML_OPS_API_URL}/v1/chat/completions",
        json=payload,
        timeout=120,
    )
    if not res.ok:
        raise Exception(f"ml-ops-api error ({res.status_code}): {res.text[:200]}")
    return res.json().get("choices", [{}])[0].get("message", {}).get("content", "")


def _call_direct(provider: str, model: str | None, messages: list, temperature: float, max_tokens: int) -> str:
    """
    Direct provider calls — fallback for local dev when securellm-bridge is not running.
    Not used in production (bridge is always available in Docker compose).
    """
    import requests as _requests

    if provider in ("tensor_forge", "local"):
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        res = _requests.post("http://localhost:8081/v1/chat/completions", json=payload, timeout=120)
        if res.ok:
            return res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        # Native llama.cpp /completion fallback
        prompt = "".join(f"{m['role'].capitalize()}: {m['content']}\n" for m in messages) + "Assistant: "
        fallback = {"prompt": prompt, "n_predict": max_tokens, "temperature": temperature, "stop": ["\nUser:", "\nHuman:"]}
        res2 = _requests.post("http://localhost:8081/completion", json=fallback, timeout=120)
        if res2.ok:
            return res2.json().get("content", "").strip()
        raise Exception(f"Tensor Forge API Error ({res2.status_code}): {res2.text}")

    if provider == "openai":
        headers = {"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}"}
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        res = _requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=60)
        if res.ok:
            return res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        raise Exception(f"OpenAI API Error: {res.text}")

    if provider == "anthropic":
        headers = {"x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""), "anthropic-version": "2023-06-01", "content-type": "application/json"}
        system_msg = "; ".join(m["content"] for m in messages if m["role"] == "system")
        anthropic_msgs = [m for m in messages if m["role"] != "system"]
        payload = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": anthropic_msgs}
        if system_msg:
            payload["system"] = system_msg
        res = _requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=60)
        if res.ok:
            return res.json().get("content", [{}])[0].get("text", "")
        raise Exception(f"Anthropic API Error: {res.text}")

    raise Exception(f"Unknown provider: {provider}")


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(request: ChatRequest):
    provider = request.llm_provider
    model = request.model

    messages = [{"role": msg.role, "content": msg.content} for msg in request.history]
    messages.append({"role": "user", "content": request.message})

    content = ""
    try:
        import requests as _requests

        # ── Fallback chain (M7.4): candle/ml-ops → securellm-bridge → direct ──
        #
        # Tier 1: ml-ops-api — local GPU inference via candle (lowest latency,
        #          on-prem, no egress). Only active when ML_OPS_ENABLED=true.
        # Tier 2: securellm-bridge — zero-trust LLM proxy; handles provider
        #          selection, rate limiting, and audit logging. Used when Tier 1
        #          is unavailable or disabled.
        # Tier 3: direct provider calls — last resort for local dev when neither
        #          ml-ops-api nor the bridge is running.
        #
        # All tiers use the OpenAI-compatible /v1/chat/completions protocol.

        used_tier: str = "unknown"

        # Tier 1: ml-ops-api (local GPU / candle)
        if ML_OPS_ENABLED:
            try:
                content = _call_via_ml_ops(model, messages, request.temperature, request.max_tokens)
                used_tier = "ml-ops-api"
            except _requests.exceptions.ConnectionError:
                logger.warning(
                    f"ml-ops-api unreachable at {ML_OPS_API_URL} — falling back to securellm-bridge"
                )
            except Exception as ml_err:
                logger.warning(f"ml-ops-api error: {ml_err} — falling back to securellm-bridge")

        # Tier 2: securellm-bridge (cloud LLM proxy)
        if not content and SECURELLM_BRIDGE_URL:
            try:
                content = _call_via_bridge(
                    provider, model, messages, request.temperature, request.max_tokens
                )
                used_tier = "securellm-bridge"
            except _requests.exceptions.ConnectionError:
                logger.warning(
                    f"securellm-bridge unreachable at {SECURELLM_BRIDGE_URL} — falling back to direct call"
                )
            except Exception as bridge_err:
                logger.warning(f"securellm-bridge error: {bridge_err} — falling back to direct call")

        # Tier 3: direct provider calls (dev fallback)
        if not content:
            content = _call_direct(
                provider, model, messages, request.temperature, request.max_tokens
            )
            used_tier = "direct"

        logger.info(f"LLM call completed via {used_tier}: provider={provider}")

    except Exception as e:
        logger.error(f"Chat generation failed (all tiers exhausted): {e}")
        content = f"Error generating text: {str(e)}"

    return ChatResponse(
        message={"content": content, "sources": []},
        conversation_id=request.conversation_id,
    )

if __name__ == "__main__":
    import uuid

    import uvicorn

    # Dev server
    uvicorn.run(app, host="0.0.0.0", port=8087)
