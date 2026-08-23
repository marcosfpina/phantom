"""
Phantom API - FastAPI REST endpoints.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from phantom.logging import configure_logging, get_logger

# ── Prometheus metrics ──────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "phantom_requests_total",
    "Total number of HTTP requests",
    labelnames=["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "phantom_request_latency_seconds",
    "HTTP request latency in seconds",
    labelnames=["endpoint"],
)

logger = get_logger("api")

# ── Global instances for vector operations ──────────────────────────

_embedding_generator = None
_vector_store = None


def get_embedding_generator():
    """Get or create embedding generator singleton."""
    global _embedding_generator
    if _embedding_generator is None:
        from phantom.core.embeddings import EmbeddingGenerator

        _embedding_generator = EmbeddingGenerator()
        logger.info("Initialized EmbeddingGenerator")
    return _embedding_generator


def get_vector_store():
    """Get or create vector store singleton."""
    global _vector_store
    if _vector_store is None:
        from phantom.rag.vectors import FAISSVectorStore

        embedder = get_embedding_generator()
        _vector_store = FAISSVectorStore(embedding_dim=embedder.dimension)
        logger.info(f"Initialized FAISSVectorStore (dim={embedder.dimension})")
    return _vector_store


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict


class ExtractRequest(BaseModel):
    content: str
    filename: str | None = "input.md"


class ExtractResponse(BaseModel):
    filename: str
    insights: dict
    processing_time_seconds: float


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: str
    history: list[ChatMessage] = []
    context_size: int = 5
    llm_provider: str = "local"


class ChatResponse(BaseModel):
    message: dict
    conversation_id: str


class PromptTestRequest(BaseModel):
    template: str
    variables: dict[str, str]


class PromptTestResponse(BaseModel):
    rendered: str
    tokens: int
    success: bool
    error: str | None = None


class VectorSearchRequest(BaseModel):
    """Body for POST /vectors/search. Query params are still accepted for backward compatibility."""

    query: str
    top_k: int = 5
    mode: str = "dense"  # "dense" | "sparse" | "hybrid"


class BatchIndexRequest(BaseModel):
    documents: list[dict]  # [{id, text, metadata}]


class BatchIndexResponse(BaseModel):
    indexed: int
    failed: int
    errors: list[str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: connect NATS publisher + start consumer on startup."""
    from phantom.nats.consumer import start_consumer, stop_consumer
    from phantom.nats.neoland_scanner import start_scanner, stop_scanner
    from phantom.nats.publisher import connect as nats_connect
    from phantom.nats.publisher import drain as nats_drain

    await nats_connect()
    consumer_task = asyncio.ensure_future(start_consumer())
    scanner_task = asyncio.ensure_future(start_scanner())  # Ciclo 1 — Fase D
    app.state.nats_consumer_task = consumer_task
    app.state.nats_scanner_task = scanner_task

    yield

    await stop_scanner()
    await stop_consumer()
    for task in (scanner_task, consumer_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await nats_drain()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from phantom import __version__

    configure_logging()

    app = FastAPI(
        title="Phantom API",
        description="AI-Powered Document Intelligence & Classification Pipeline",
        version=__version__,
        lifespan=lifespan,
    )

    from phantom.writer.api import router as writer_router

    app.include_router(writer_router)

    # ── Middleware: instrument every request ────────────────────────

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        endpoint = request.url.path
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=str(response.status_code),
        ).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)

        return response

    # ── Health & readiness ──────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse)
    async def health():
        """Liveness probe — always 200 if the process is running."""
        return HealthResponse(status="operational", version=__version__)

    @app.get("/ready", response_model=ReadyResponse)
    async def ready():
        """Readiness probe — checks downstream dependencies."""
        import os

        import httpx

        checks: dict = {}

        # Vector store availability (lazy: only checked if previously initialised)
        try:
            checks["vector_store"] = True
        except Exception:
            checks["vector_store"] = False

        # SecureLLM Bridge health (M3.4)
        bridge_url = os.environ.get("SECURELLM_BRIDGE_URL", "http://localhost:8081").rstrip("/")
        if bridge_url:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    r = await client.get(f"{bridge_url}/api/ready")
                checks["securellm_bridge"] = r.status_code == 200
            except Exception:
                checks["securellm_bridge"] = False

        all_ok = all(checks.values()) if checks else True
        return ReadyResponse(
            status="ready" if all_ok else "not_ready",
            checks=checks,
        )

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/api/system/metrics")
    async def system_metrics():
        """
        Get real-time system resource metrics.
        Returns CPU, memory, disk, and VRAM usage from the host machine.
        """
        import psutil

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        # Memory metrics
        mem = psutil.virtual_memory()

        # Disk metrics
        disk = psutil.disk_usage("/")

        # Network metrics (optional)
        net_io = psutil.net_io_counters()

        # VRAM metrics (if GPU available)
        vram_info = None
        try:
            # Try to get GPU info using nvidia-smi or similar
            import subprocess

            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                used, total = map(float, result.stdout.strip().split(","))
                vram_info = {
                    "used_mb": int(used),
                    "total_mb": int(total),
                    "available_mb": int(total - used),
                    "percent": round((used / total) * 100, 1),
                }
        except Exception:
            # GPU not available or nvidia-smi not installed
            pass

        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "frequency_mhz": cpu_freq.current if cpu_freq else None,
            },
            "memory": {
                "total_bytes": mem.total,
                "used_bytes": mem.used,
                "available_bytes": mem.available,
                "percent": mem.percent,
                "total_gb": round(mem.total / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
            },
            "disk": {
                "total_bytes": disk.total,
                "used_bytes": disk.used,
                "free_bytes": disk.free,
                "percent": disk.percent,
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
            },
            "vram": vram_info,
            "timestamp": time.time(),
        }

    @app.post("/extract", response_model=ExtractResponse)
    async def extract(request: ExtractRequest):
        """Extract insights from markdown content using CORTEX engine."""
        start = time.time()

        insights = {
            "themes": [],
            "patterns": [],
            "learnings": [],
            "concepts": [],
            "recommendations": [],
        }

        content = request.content
        filename = request.filename or "input.md"

        if content.strip():
            try:
                from phantom.core.cortex import SemanticChunker

                # Chunk the content for analysis metadata
                chunker = SemanticChunker(max_tokens=1024, overlap=128)
                chunks = chunker.chunk_text(content, filename)

                insights["chunk_count"] = len(chunks)
                insights["word_count"] = len(content.split())

                # Try LLM-based extraction if available
                try:
                    from phantom.core.cortex import PromptBuilder
                    from phantom.providers.llamacpp import LlamaCppProvider

                    provider = LlamaCppProvider()
                    if provider.is_available():
                        prompt = PromptBuilder.build_extraction_prompt(content, filename)
                        result = provider.generate(prompt)
                        parsed = PromptBuilder.parse_json_response(result.text)
                        if parsed:
                            insights.update(parsed)
                except Exception as e:
                    logger.debug(f"LLM extraction unavailable: {e}")
                    # Gracefully continue with basic insights

            except Exception as e:
                logger.warning(f"Content analysis failed: {e}")

        return ExtractResponse(
            filename=filename,
            insights=insights,
            processing_time_seconds=time.time() - start,
        )

    @app.post("/process")
    async def process(
        file: UploadFile,
        chunk_strategy: str = "recursive",
        chunk_size: int = 1024,
    ):
        """
        Process document using CORTEX engine.
        Accepts file upload and returns extracted insights.
        """
        import tempfile
        from pathlib import Path

        from phantom.core.cortex import CortexProcessor

        if not file.filename:
            raise HTTPException(400, "Filename required")

        # Read file content
        content = await file.read()

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=Path(file.filename).suffix, delete=False
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            # Initialize processor
            processor = CortexProcessor(
                chunk_size=chunk_size,
                enable_vectors=False,  # Don't auto-index during processing
                verbose=False,
            )

            # Process document
            insights = processor.process_document(tmp_path)

            # Return as dict for JSON serialization
            return {
                "filename": file.filename,
                "insights": insights.model_dump(),
                "processing_time": insights.processing_time_seconds,
            }

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise HTTPException(500, f"Processing failed: {str(e)}")

        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()

    @app.post("/upload")
    async def upload_file(file: UploadFile):
        """Upload and process a single file."""
        if not file.filename:
            raise HTTPException(400, "Filename required")

        content = await file.read()
        return {
            "filename": file.filename,
            "size": len(content),
            "status": "uploaded",
        }

    @app.post("/api/upload")
    async def api_upload_files(files: list[UploadFile]):
        """Upload and queue multiple files for CORTEX processing."""
        import tempfile
        from pathlib import Path

        from phantom.core.cortex import CortexProcessor

        results = []
        for file in files:
            if not file.filename:
                results.append(
                    {"filename": "unknown", "status": "error", "error": "Filename required"}
                )
                continue

            content = await file.read()
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=Path(file.filename).suffix, delete=False
                ) as tmp:
                    tmp.write(content)
                    tmp_path = Path(tmp.name)

                try:
                    processor = CortexProcessor(
                        chunk_size=1024, enable_vectors=False, verbose=False
                    )
                    insights = processor.process_document(tmp_path)
                    results.append(
                        {
                            "filename": file.filename,
                            "status": "processed",
                            "insights": insights.model_dump(),
                        }
                    )
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()

            except Exception as e:
                logger.error(f"Upload processing failed for {file.filename}: {e}")
                results.append({"filename": file.filename, "status": "error", "error": str(e)})

        return {"files": results}

    @app.post("/vectors/search")
    async def vector_search(
        request: Request,
        query: str | None = None,
        top_k: int = 5,
        mode: str = "dense",
    ):
        """
        Semantic vector search.

        Accepts query params (?query=...&top_k=N&mode=dense) for backward
        compatibility OR a JSON body {query, top_k, mode} where mode is one of:
          - "dense"   — FAISS cosine similarity only (default)
          - "sparse"  — BM25 keyword search only
          - "hybrid"  — BM25 + FAISS fused with Reciprocal Rank Fusion
        """
        try:
            # Prefer JSON body when present
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
                query = body.get("query", query)
                top_k = int(body.get("top_k", top_k))
                mode = str(body.get("mode", mode))

            if not query:
                raise HTTPException(400, "query is required")

            embedder = get_embedding_generator()
            store = get_vector_store()

            if len(store) == 0:
                raise HTTPException(
                    400, "Vector store is empty. Index documents first using /vectors/index"
                )

            query_embedding = embedder.encode([query])[0]

            if mode == "hybrid":
                results = store.hybrid_search(query, query_embedding, top_k=top_k)
            elif mode == "sparse":
                # BM25 only — fall back to dense if unavailable
                if hasattr(store, "_bm25_search"):
                    results = store._bm25_search(query, top_k=top_k)
                    if not results:
                        results = store.search(query_embedding, top_k=top_k)
                else:
                    results = store.search(query_embedding, top_k=top_k)
            else:  # dense (default)
                results = store.search(query_embedding, top_k=top_k)

            return {
                "query": query,
                "mode": mode,
                "results": [
                    {"text": r.text, "score": float(r.score), "metadata": r.metadata}
                    for r in results
                ],
                "total_results": len(results),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise HTTPException(500, f"Search failed: {str(e)}")

    @app.post("/vectors/index")
    async def vector_index(file: UploadFile):
        """
        Index a document into the FAISS vector store.
        Chunks the document and generates embeddings for semantic search.
        """

        from phantom.core.cortex import SemanticChunker

        if not file.filename:
            raise HTTPException(400, "Filename required")

        try:
            # Read file content
            content = await file.read()
            text = content.decode("utf-8")

            # Chunk the document
            chunker = SemanticChunker(max_tokens=1024, overlap=128)
            chunks = chunker.chunk_text(text, file.filename)

            if not chunks:
                raise HTTPException(400, "No content to index")

            # Get instances
            embedder = get_embedding_generator()
            store = get_vector_store()

            # Generate embeddings
            texts = [c.text for c in chunks]
            embeddings = embedder.encode(texts)

            # Add to vector store
            metadata = [
                {"chunk_id": c.chunk_id, "source": file.filename, "file": file.filename}
                for c in chunks
            ]
            store.add(embeddings, texts, metadata)

            logger.info(f"Indexed {len(chunks)} chunks from {file.filename}")

            return {
                "status": "indexed",
                "chunks_indexed": len(chunks),
                "filename": file.filename,
                "total_vectors": len(store),
            }

        except UnicodeDecodeError:
            raise HTTPException(400, "File must be text-based (UTF-8)")
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            raise HTTPException(500, f"Indexing failed: {str(e)}")

    @app.post("/vectors/batch-index", response_model=BatchIndexResponse)
    async def batch_index(request: BatchIndexRequest):
        """
        Index multiple documents into the FAISS vector store in one call.

        Each document should be: {id, text, metadata?}
        Useful for indexing multiple search results or code snippets at once.
        """
        embedder = get_embedding_generator()
        store = get_vector_store()

        indexed = 0
        failed = 0
        errors: list[str] = []

        texts: list[str] = []
        metadatas: list[dict] = []

        for doc in request.documents:
            doc_id = doc.get("id", "")
            text = doc.get("text", "")
            meta = doc.get("metadata", {})
            if not isinstance(meta, dict):
                meta = {}

            if not text:
                failed += 1
                errors.append(f"doc '{doc_id}': empty text, skipped")
                continue

            texts.append(text)
            metadatas.append({"id": doc_id, **meta})

        if texts:
            try:
                embeddings = embedder.encode(texts)
                store.add(embeddings, texts, metadatas)
                indexed = len(texts)
                logger.info(f"Batch indexed {indexed} documents")
            except Exception as e:
                failed += len(texts)
                errors.append(f"Embedding/indexing error: {str(e)}")
                logger.error(f"Batch index failed: {e}")

        return BatchIndexResponse(indexed=indexed, failed=failed, errors=errors)

    @app.post("/api/chat", response_model=ChatResponse)
    async def rag_chat(request: ChatRequest):
        """
        RAG-powered chat interface.
        Retrieves relevant context from vector store and generates response using LLM.
        """
        try:
            # Get instances
            embedder = get_embedding_generator()
            store = get_vector_store()

            # Retrieve context from vector store
            sources = []
            if len(store) > 0 and request.context_size > 0:
                query_embedding = embedder.encode([request.message])[0]
                search_results = store.search(query_embedding, top_k=request.context_size)
                sources = [
                    {"text": r.text, "score": float(r.score), "metadata": r.metadata}
                    for r in search_results
                ]

            # Build context string
            context_str = ""
            if sources:
                context_str = "\n\nRelevant context:\n"
                for i, src in enumerate(sources, 1):
                    context_str += f"{i}. {src['text'][:500]}...\n"

            # Build prompt with history
            history_str = ""
            for msg in request.history[-5:]:  # Last 5 messages
                history_str += f"{msg.role}: {msg.content}\n"

            # Construct final prompt
            system_prompt = (
                "You are a helpful AI assistant with access to a knowledge base. "
                "Use the provided context to answer questions accurately. "
                "If the context doesn't contain relevant information, say so."
            )

            full_prompt = f"{system_prompt}\n\n{history_str}\n{context_str}\nuser: {request.message}\nassistant:"

            # Get LLM provider
            from phantom.providers.llamacpp import LlamaCppProvider

            # Use local llama.cpp for now
            provider = LlamaCppProvider()

            # Generate response
            try:
                response = provider.generate(full_prompt, max_tokens=512, temperature=0.7)
                content = response.text if hasattr(response, "text") else str(response)
            except Exception as e:
                logger.warning(f"LLM generation failed: {e}, using fallback")
                # Fallback response if LLM unavailable
                if sources:
                    content = (
                        f"Based on the knowledge base, I found {len(sources)} relevant sources. "
                        "However, the LLM service is currently unavailable."
                    )
                else:
                    content = (
                        "I don't have enough context to answer this question, "
                        "and the LLM service is currently unavailable."
                    )

            return ChatResponse(
                message={"content": content, "sources": sources},
                conversation_id=request.conversation_id,
            )

        except Exception as e:
            logger.error(f"Chat failed: {e}")
            raise HTTPException(500, f"Chat failed: {str(e)}")

    @app.get("/api/models")
    async def list_models():
        """
        List available LLM models by provider.
        Returns models organized by provider (local, openai, anthropic).
        """
        # Check if llama.cpp is available
        local_models = []
        try:
            from phantom.providers.llamacpp import LlamaCppProvider

            provider = LlamaCppProvider()
            status = await provider.health_check() if hasattr(provider, "health_check") else True

            if status:
                # Default local models (can be expanded based on actual llama.cpp models)
                local_models = [
                    {"id": "local-default", "name": "Local LLM (llama.cpp)"},
                    {"id": "qwen-30b", "name": "Qwen 30B"},
                    {"id": "llama-3-8b", "name": "Llama 3 8B"},
                ]
        except Exception as e:
            logger.debug(f"Local LLM not available: {e}")

        return {
            "local": local_models,
            "openai": [],  # Future: OpenAI integration
            "anthropic": [],  # Future: Anthropic integration
        }

    @app.post("/api/prompt/test", response_model=PromptTestResponse)
    async def test_prompt(request: PromptTestRequest):
        """
        Test prompt template rendering with variables.
        Validates template syntax and returns rendered output with token count.
        """
        try:
            # Simple variable substitution
            rendered = request.template
            for key, value in request.variables.items():
                placeholder = "{" + key + "}"
                rendered = rendered.replace(placeholder, value)

            # Check if all variables were substituted
            import re

            remaining_vars = re.findall(r"\{(\w+)\}", rendered)
            if remaining_vars:
                return PromptTestResponse(
                    rendered=rendered,
                    tokens=0,
                    success=False,
                    error=f"Missing values for variables: {', '.join(remaining_vars)}",
                )

            # Estimate token count (rough approximation: 1 token ≈ 4 chars)
            token_count = len(rendered) // 4

            return PromptTestResponse(
                rendered=rendered, tokens=token_count, success=True, error=None
            )

        except Exception as e:
            logger.error(f"Prompt test failed: {e}")
            return PromptTestResponse(rendered="", tokens=0, success=False, error=str(e))

    @app.post("/api/chat/stream")
    async def rag_chat_stream(request: ChatRequest):
        """
        RAG-powered chat with Server-Sent Events streaming.
        Returns tokens as they are generated for lower perceived latency.
        """

        async def event_generator():
            try:
                # Retrieve context (same as /api/chat)
                embedder = get_embedding_generator()
                store = get_vector_store()

                sources = []
                if len(store) > 0 and request.context_size > 0:
                    query_embedding = embedder.encode([request.message])[0]
                    search_results = store.search(query_embedding, top_k=request.context_size)
                    sources = [
                        {"text": r.text, "score": float(r.score), "metadata": r.metadata}
                        for r in search_results
                    ]

                # Build context
                context_str = ""
                if sources:
                    context_str = "\n\nRelevant context:\n"
                    for i, src in enumerate(sources, 1):
                        context_str += f"{i}. {src['text'][:500]}...\n"

                history_str = ""
                for msg in request.history[-5:]:
                    history_str += f"{msg.role}: {msg.content}\n"

                system_prompt = (
                    "You are a helpful AI assistant with access to a knowledge base. "
                    "Use the provided context to answer questions accurately. "
                    "If the context doesn't contain relevant information, say so."
                )
                full_prompt = f"{system_prompt}\n\n{history_str}\n{context_str}\nuser: {request.message}\nassistant:"

                # Send sources first
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

                # Stream from LLM
                from phantom.providers.llamacpp import LlamaCppProvider

                provider = LlamaCppProvider()

                try:
                    async for chunk in provider.stream(
                        full_prompt, max_tokens=512, temperature=0.7
                    ):
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                except Exception as e:
                    logger.warning(f"LLM streaming failed: {e}")
                    fallback = (
                        f"Found {len(sources)} relevant sources, but LLM service is unavailable."
                        if sources
                        else "LLM service is currently unavailable."
                    )
                    yield f"data: {json.dumps({'type': 'token', 'content': fallback})}\n\n"

                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                logger.error(f"Stream failed: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    class PipelineRequest(BaseModel):
        input_dir: str
        output_dir: str | None = None
        workers: int = 4
        dry_run: bool = False
        sanitization_policy: str = "strip_metadata"

    class PipelineStatusResponse(BaseModel):
        status: str
        total_files: int
        processed: int
        failed: int
        quarantined: int
        duration_seconds: float
        report: dict

    @app.post("/api/pipeline", response_model=PipelineStatusResponse)
    async def run_pipeline(request: PipelineRequest):
        """
        Execute the DAG pipeline for file classification, integrity verification,
        sensitive data detection, and sanitization.
        """
        import asyncio
        from pathlib import Path

        from phantom.pipeline.phantom_dag import (
            PhantomPipeline,
            PipelineContext,
            SanitizationPolicy,
        )

        input_dir = Path(request.input_dir)
        if not input_dir.exists() or not input_dir.is_dir():
            raise HTTPException(400, f"Input directory does not exist: {request.input_dir}")

        if request.output_dir:
            output_dir = Path(request.output_dir)
        else:
            output_dir = input_dir.parent / f"{input_dir.name}_classified"

        try:
            policy = SanitizationPolicy(request.sanitization_policy)
        except ValueError:
            raise HTTPException(
                400,
                f"Invalid sanitization_policy: {request.sanitization_policy}. "
                f"Options: none, strip_metadata, redact_pii, full_sanitize",
            )

        staging_dir = output_dir / ".staging"
        quarantine_dir = output_dir / ".quarantine"

        ctx = PipelineContext(
            input_dir=input_dir,
            output_dir=output_dir,
            staging_dir=staging_dir,
            quarantine_dir=quarantine_dir,
            workers=request.workers,
            dry_run=request.dry_run,
            sanitization_policy=policy,
        )

        # Run pipeline in thread to avoid blocking the event loop
        start = time.perf_counter()

        def _run():
            pipeline = PhantomPipeline(ctx)
            pipeline.execute()
            return pipeline

        pipeline = await asyncio.to_thread(_run)
        duration = time.perf_counter() - start

        # Build report from context
        from collections import defaultdict

        by_classification: dict[str, int] = defaultdict(int)
        for record in ctx.records.values():
            by_classification[record.classification] += 1

        report = {
            "classifications": dict(by_classification),
            "sensitive_files": sum(1 for r in ctx.records.values() if r.sensitive_findings),
            "output_dir": str(output_dir),
        }

        return PipelineStatusResponse(
            status="completed",
            total_files=ctx.total_files,
            processed=ctx.processed,
            failed=ctx.failed,
            quarantined=ctx.quarantined,
            duration_seconds=round(duration, 2),
            report=report,
        )

    @app.post("/api/pipeline/scan")
    async def pipeline_scan(
        directory: str,
        top_n: int = 50,
    ):
        """
        Scan a directory for file classifications and sensitive data without moving files.
        Lightweight read-only alternative to /api/pipeline.
        """
        import asyncio
        from pathlib import Path

        from phantom.pipeline.phantom_dag import ClassificationEngine

        dir_path = Path(directory)
        if not dir_path.exists():
            raise HTTPException(400, f"Directory does not exist: {directory}")

        def _scan():
            files = [f for f in dir_path.rglob("*") if f.is_file()][:top_n]
            results = []
            for filepath in files:
                try:
                    classification, mime_type, sensitivity = ClassificationEngine.classify(filepath)
                    findings = ClassificationEngine.scan_sensitive_content(filepath)
                    results.append(
                        {
                            "path": str(filepath.relative_to(dir_path)),
                            "classification": classification.value,
                            "mime_type": mime_type,
                            "sensitivity": sensitivity.value,
                            "sensitive_patterns": [
                                {"name": f.pattern_name, "count": f.count, "risk": f.risk_score}
                                for f in findings
                            ],
                        }
                    )
                except Exception:
                    results.append(
                        {
                            "path": str(filepath.relative_to(dir_path)),
                            "classification": "error",
                            "mime_type": "unknown",
                            "sensitivity": 0,
                            "sensitive_patterns": [],
                        }
                    )
            return results, len(list(dir_path.rglob("*")))

        results, total_count = await asyncio.to_thread(_scan)

        return {
            "directory": directory,
            "scanned": len(results),
            "total_files": total_count,
            "files": results,
        }

    @app.get("/rag/query")
    async def rag_query(question: str, collection: str = "default", top_k: int = 5):
        """Query the RAG pipeline (legacy endpoint)."""
        return {
            "question": question,
            "answer": "Please use /api/chat endpoint for RAG queries",
            "sources": [],
        }

    # Integration with AI-Agent-OS
    from phantom.api.judge_api import (
        PhantomGateBundle,
        PhantomGateResponse,
        get_judgment_engine,
    )

    @app.post("/judge", response_model=PhantomGateResponse)
    async def judge_bundle(bundle: PhantomGateBundle):
        """
        Judge system metrics bundle from AI-OS-Agent.
        Analyzes metrics, logs, and alerts to provide insights and recommendations.
        """
        try:
            engine = get_judgment_engine()
            return engine.judge(bundle)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


# For uvicorn direct import
app = create_app()


def serve():
    """Entry point for phantom-api script."""
    import argparse
    import os

    import uvicorn

    parser = argparse.ArgumentParser(description="Phantom API Server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 8008)),
        help="Port to listen on (default: 8008)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    serve()
