# Release v0.1.0 — Alpha

**Released**: 2026-05-02

This is the first public Alpha release of Phantom — a local-first AI document intelligence framework.

## What's Included

### Core Engine
- **CORTEX Processor**: Semantic chunking, parallel LLM classification, and insight extraction
- **FAISS Vector Store**: Semantic search with sentence-transformers embeddings
- **RAG Pipeline**: Context-aware question-answering over indexed document collections
- **Sentiment Engine**: NLTK VADER-based scoring with optional spaCy NER

### API Server
- FastAPI REST server with Prometheus metrics, SSE streaming, and health/readiness endpoints
- Document upload, processing, vector indexing, and RAG chat endpoints

### CLI
- Typer-based `phantom` CLI for document extraction, analysis, classification, and scanning

### Desktop App
- Tauri 2.0 + SvelteKit + Svelte 5 desktop UI (Chat, Process, Search, Workbench, Library, Settings tabs)

### Rust Agent (`intelagent`)
- Multi-crate workspace: security, governance, memory, quality, MCP protocol handlers

### Infrastructure
- Nix flake with hermetic, reproducible build environment
- 8 GitHub Actions workflows (CI, release, secret scanning, flake updates)
- Pre-commit hooks (Ruff, YAML, import sanity)
- 26 test files with 70% coverage threshold

## Monorepo Reorganization (since last tag)
- Consolidated repository structure into public-release layout
- Reorganized `docs/` into categorized subdirectories (Architecture, Development, API, Guides, Reference, History)
- Moved deprecated code and old architecture snapshots to `.archive/`
- Refreshed `README.md` with accurate project status and roadmap

## Requirements
- Python 3.11+
- Nix (recommended for reproducible dev environment)
- llama.cpp server for local LLM inference

## Known Limitations
- Cloud LLM providers (OpenAI, Anthropic, DeepSeek) are stubbed, not yet implemented
- Kubernetes/Helm packaging not included
- Frontend e2e tests (Playwright) not yet configured

## Installation

```bash
# Via Nix
nix develop github:kernelcore/phantom

# Via pip
pip install phantom==0.1.0
```
