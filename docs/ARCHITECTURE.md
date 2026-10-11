# Architecture

## System Purpose

PHANTOM is a sovereign document intelligence engine. It classifies, sanitizes and semantically
searches documents without the data leaving the host. It exists because the usual answer to
document intelligence — ship the corpus to a cloud API — is unacceptable for regulated or
privileged material under LGPD and GDPR.

Everything runs locally by default. Cloud providers are swappable adapters, not requirements.

## High-Level Overview

```
Document in
  │
  ▼
┌──────────────────────────────────────────────────┐
│ pipeline/  — CORTEX                              │
│   semantic chunking → embeddings                 │
│   → LLM classification → Pydantic schema         │
└──────────────┬───────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────┐
│ Sanitization DAG                                 │
│   strip_metadata → redact_pii → full_sanitize    │
│   (CPF / CNPJ aware)                             │
└──────────────┬───────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────┐
│ rag/ — hybrid retrieval                          │
│   FAISS (dense cosine) ⊕ BM25 (sparse)           │
│   fused by Reciprocal Rank Fusion                │
└──────────────┬───────────────────────────────────┘
               ▼
      api/ — 20 typed FastAPI endpoints
               │
   ┌───────────┼───────────┬──────────┐
   ▼           ▼           ▼          ▼
 cerebro    neotron      NATS    cortex-desktop
 (RAG)     (SENTINEL)  (events)  (Tauri + SvelteKit)
```

## Components

| Package | Files | Responsibility |
|---|---|---|
| `src/phantom/analysis/` | 6 | Document analysis and judgment |
| `src/phantom/writer/` | 4 | Output generation |
| `src/phantom/rag/` | 4 | Hybrid retrieval, FAISS + BM25 + RRF |
| `src/phantom/providers/` | 4 | LLM provider adapters (llama.cpp, cloud) |
| `src/phantom/nats/` | 4 | Event mesh integration |
| `src/phantom/core/` | 4 | Domain types, configuration |
| `src/phantom/api/` | 4 | FastAPI surface, 20 typed endpoints |
| `src/phantom/neotron/` | 3 | NEUTRON / SENTINEL compliance integration |
| `src/phantom/cerebro/` | 3 | CEREBRO RAG client |
| `src/phantom/pipeline/` | 2 | CORTEX ingestion pipeline |
| `src/phantom/cli/` | 2 | Command-line interface |

`cortex-desktop/` holds the Tauri 2 + SvelteKit desktop client. `apps/` and `arch/` hold
supporting applications and architecture notes.

### VRAM Guardian

Ingestion is GPU-bound. A guardian polls the NVIDIA Management Library at 50 Hz and throttles
the ingestion pipeline above 92% VRAM utilization, so a large corpus cannot drive the GPU into
out-of-memory mid-run.

## Data Flow

1. Document enters via CLI or API.
2. CORTEX chunks it semantically, embeds each chunk, classifies with an LLM, and validates the
   result against a Pydantic schema.
3. The sanitization DAG runs `strip_metadata` → `redact_pii` → `full_sanitize`, with
   Brazilian CPF and CNPJ patterns handled explicitly.
4. Chunks are indexed into FAISS (dense) and a BM25 index (sparse).
5. Queries retrieve from both and fuse the rankings via Reciprocal Rank Fusion.
6. Results are returned through the API, and judgments may be published to NATS.

## Trust Boundaries

| Boundary | Control |
|---|---|
| Caller → API | reached via securellm-mcp, itself behind the bridge |
| Document → index | sanitization DAG runs before anything is persisted |
| PHANTOM → LLM | local llama.cpp by default; no egress required |
| PHANTOM → NATS | best-effort event publication |

The critical property is that a document's PII is removed **before** indexing, not at query
time, so the index itself is safe to persist.

## Runtime Model

Python 3.11+, FastAPI, async. Ingestion is throttled by the VRAM guardian. The desktop client
is a separate Tauri process communicating over the local API.

## Configuration

Environment-driven, validated with Pydantic v2. Provider selection is a configuration
concern; the abstraction covers llama.cpp and cloud providers uniformly.

## Storage

- FAISS index for dense vectors.
- BM25 index for sparse retrieval.
- Sanitized document store; originals are not retained post-sanitization by default.

## External Integrations

| Target | Purpose | Required |
|---|---|---|
| llama.cpp | local inference and embeddings | default path |
| cerebro :8009 | RAG over the ADR knowledge base | no |
| neotron | SENTINEL compliance judgments | no |
| NATS :4222 | judgment events | no |

## Security Model

- Local-first: the default configuration makes no outbound request.
- PII sanitization is a pipeline stage, not an option — CPF/CNPJ redaction runs before
  indexing.
- `SECURITY.md` is present in the repository.
- Structured logging with structlog; Prometheus metrics exposed.

## Testing Model

38 test files. `nix develop` then `pytest`. The flake exposes `packages`, `checks`, `apps`,
`overlays` and `nixosModules` — the most complete build contract in the ecosystem alongside
`sentinel`.

## Operational Notes

- Health probe, structured logging, Prometheus metrics, graceful shutdown.
- Runs on port 8008 from `deploy/docker-compose.master.yml`, fronted by `phantom-proxy`.
- 6 release tags — the strongest release discipline in the ecosystem.
- Build: `nix develop`, then `pytest` and the `phantom` CLI.

## Known Architectural Risks

1. **Security posture scores 45/100** despite being the component that handles the most
   sensitive data. `SECURITY.md` exists but there is no threat model, no SBOM in the release
   pipeline and no secret scanning in CI.
2. **No operational runbook.**
3. **Architecture depth scores 18/100** — 11 packages with no recorded module contracts; the
   `neotron` and `cerebro` client packages couple PHANTOM to two sibling services without an
   ADR describing the contract.
4. **Sanitization correctness is not property-tested.** CPF/CNPJ redaction is the security
   boundary of the whole system and is covered by example-based tests only.
5. **VRAM guardian threshold (92%) is hard-coded** rather than configurable per GPU.
6. **`.archive/` and `demo_input/` are committed**, adding noise to the repository surface.
