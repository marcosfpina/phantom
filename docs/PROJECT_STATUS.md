# Ecosystem Project Status
**Last Updated**: 2026-04-26  
**Maintainer**: marcosfpina  
**Fonte**: merge de todos os roadmaps fragmentados do ecossistema

---

## Mapa do Ecossistema

```
                        ┌─────────────────────┐
                        │     ADR LEDGER       │
                        │  (Governance Layer)  │
                        │  knowledge_base.json │
                        └──────────┬──────────┘
                                   │ ADR policies + knowledge artifacts
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────▼───────┐  ┌────────▼───────┐  ┌────────▼───────┐
     │    CEREBRO     │  │    PHANTOM     │  │    SPECTRE     │
     │  (RAG/Retriev) │  │ (ML/Desktop)  │  │ (Infra/Events) │
     └────────────────┘  └────────┬───────┘  └────────┬───────┘
                                  │ NATS events        │ NATS bus
                         ┌────────▼───────────────────▼───────┐
                         │            SENTINEL                  │
                         │    (Orchestration / Platform)        │
                         └────────────────┬───────────────────┘
                                          │ compliance events
                         ┌────────────────▼───────────────────┐
                         │             NEOTRON                 │
                         │  (Agent Compliance + Guardrails)    │
                         │  SENTINEL · BASTION · CORTEX        │
                         └────────────────┬───────────────────┘
                                          │ OPA policy eval
                         ┌────────────────▼───────────────────┐
                         │         securellm-mcp               │
                         │     (80+ MCP tools / backend)       │
                         └────────────────────────────────────┘

     spider-nix ──► NixOS build tooling (shared across projetos)
     neoland    ──► Scanner agent (integrado ao neotron via NATS)
```

---

## ADR Ledger (Core — Governance Layer)

**Status**: Beta v0.1.0 · Public release pendente  
**ADRs**: 56 total (31 accepted · 18 proposed · 2 superseded)

| Fase | Status | Descrição |
|------|--------|-----------|
| Phase 0 — Foundation | ✅ | adr-ledger em prod, NixOS base, CLI, schema, OPA |
| Phase 0 (cont.) | 🔄 | IAM policies (módulos Nix operacionais, smoke test pendente) |
| Phase 0 (cont.) | 🔄 | Algorand integration (roadmap) |
| Phase 1 — Sovereignty | ⬜ | Radicle policy versioning, soulbound identity, hash chain |
| Phase 2 — Governance | ⬜ | Quadratic voting, conviction voting, multi-party approvals |
| Phase 3 — Protocol | ⬜ | Spec formal AGP, SDK, paper público |
| Phase 4 — Ecosystem | ⬜ | Outros projetos adotando, GaaS, standards track |

**Enforcement layer (Nix modules)**:
- `nix/modules/adr-ledger-iam.nix` — IAM + systemd services por agente ✅
- `nix/iam/policy-engine.nix` — OPA server daemon NixOS ✅
- `nix/iam/sandboxing.nix` — sandboxing per-agent (FS + rede + caps + syscalls) ✅
- `policies/adr/authz.rego` — OPA authz policy (6 roles, allow/deny branches) ✅
- Smoke test 6/6 PASS (`tests/smoke_enforcement.sh`) ✅

**Release gate**:
- [ ] `nix flake check` verde
- [x] `nixosModules.adr-ledger-agents` exportado e documentado no README
- [ ] Smoke test: deny confirmado em ação fora de allowedActions
- [ ] `knowledge/*.json` sincronizado (`adr sync`)
- [ ] GitHub Release com changelog + known issues

---

## neotron (NEXUS — Agent Compliance + Guardrails)

**Rating**: 8.1/10 · **Last updated**: 2026-03-09  
**Última sessão**: fix collection errors + LGPDConsent bug + datetime deprecations

| Fase | Status | Entregável |
|------|--------|-----------|
| Phase 0 — Reorganização | ✅ | Estrutura `neutron/`, build configs |
| Phase 1 — SENTINEL | ✅ | Guardrails declarativos, audit logger, severities block/warn/audit |
| Phase 2 — BASTION | ✅ | seccomp-BPF syscall filtering (kernel-level) |
| Phase 3 — Multi-Reg Auditors | ✅ | LGPD (Art. 18, 20), GDPR (Art. 15, 17, 22), EU AI Act (Art. 5, 13, 14) |
| Phase 4 — Smart Contracts | ✅ | ComplianceGuardrail.sol, LGPDConsent.sol, AuditLogger.sol — 69 testes Solidity |
| Phase 5 — CORTEX | ✅ | AgentSwarm + 4 consensus strategies + LLM real (Claude sonnet-4-6) |
| Phase 6 — ORACLE | ✅ | 5 explanation strategies, múltiplos formatos de saída |
| Phase 7 — SYNAPSE | ✅ | Working memory, pgvector schema — **embedding pipeline ausente** |
| Phase 8 — Decentralized Storage | ✅ | IPFS + Arweave audit log |
| Phase 9 — LLM Integration | ✅ | Anthropic/OpenAI/DeepSeek/LlamaCpp, fallback chain + circuit breaker |
| Phase 10 — API Hardening | ✅ | FastAPI + JWT + rate limiting, todos os routers |
| Phase 11 — SOPS Connector | ✅ | `/run/secrets/` + env vars fallback |

**Gaps críticos (pendentes)**:
- SYNAPSE: embedding pipeline não conectado ao pgvector
- `api_secret_key` ausente → API em open mode (sem auth JWT real)
- Frontend: validar conexão wagmi config → contratos deployados
- Stubs vazios: `test_specialized.py`, `test_providers.py`

**Integração com adr-ledger**: compliance events via NATS → OPA bundle (policy eval contra ADRs)

---

## phantom (ML Classification + Desktop)

**Última atividade**: 2026-04-25 (rename neutron → neotron + neoland scanner)

| Status | Entregável |
|--------|-----------|
| ✅ Shipped | CLI completo (extract, analyze, classify, scan, rag, tools) |
| ✅ Shipped | REST API 22 endpoints + Prometheus metrics |
| ✅ Shipped | FAISS + BM25 hybrid search (RRF), embeddings, semantic chunking |
| ✅ Shipped | SSE streaming chat + RAG ingestion/query |
| ✅ Shipped | Cortex Desktop — Tauri 2.0 + SvelteKit 5, 6 tabs |
| ✅ Shipped | IntelAgent core (Agent, Task, Context, Proof, QualityGate traits) |
| ✅ Shipped | IntelAgent SOC kernel (scheduler, task queue, agent pool, event bus) |
| 🔄 Em progresso | Frontend sub-components (MessageBubble, FileUploader, ErrorToast) |
| 🔄 Em progresso | Frontend test infra — Vitest + Playwright |
| ⬜ Planned | Metrics dashboard tab, markdown/code rendering no chat |
| ⬜ Planned | IntelAgent crates restantes (security, governance, memory, quality, mcp, cli) |
| ⬜ Planned | Redis cache para embeddings e queries |
| ⬜ Planned | Standalone binaries Linux/macOS + Docker/OCI |
| ⬜ Long term | Cloud LLM providers, NixOS module, ZK proofs, DAO governance |

> **Nota**: `phantom-ray/.../intelagent/` é cópia obsoleta (2026-01-14). Canônico em `phantom/intelagent/`.

---

## spectre (Core Infrastructure — Event Bus + Proxy + Observability)

**Última atividade**: 2026-04-17 (flake.lock update)  
**Arquitetura**: infraestrutura core only — domain services em repos separados

| Fase | Status | Cobertura |
|------|--------|-----------|
| Phase 0 — Foundation | ✅ COMPLETE (100%) | Monorepo, crates, NATS event bus |
| Phase 1 — Security Infrastructure | ✅ COMPLETE (100%) | spectre-secrets, spectre-proxy, E2E |
| Phase 2 — Observability | ⏳ IN PROGRESS (50%) | lib pronta; infra Docker + dashboard pendente |

**Pendente na Phase 2**:
- Jaeger/Tempo + Prometheus + Grafana no `docker-compose.yml`
- `/metrics` endpoint no `spectre-proxy`
- Verificar trace propagation cross-NATS

**Infra atual**: NATS (4222) ✅ · TimescaleDB (5432) ✅ · Neo4j (7687) ✅  
**Testes**: ~35 (unit + integration), cobertura ~92%

---

## sentinel (Orchestration Layer / Platform Umbrella)

**Última atividade**: 2026-04-19 (absorção do master orchestration repo)  
**Decision**: **GO** em 2026-03-30

| Batch | Status | Data |
|-------|--------|------|
| Batch 1 — Bring-up + Smoke | ✅ PASS | 2026-03-30 |
| Batch 2 — Live E2E | ✅ PASS | 2026-03-30 (9 passed, 3 skipped) |
| Batch 3 — Security | ✅ PASS | 2026-03-30 (14 passed, TLS/mTLS PASS) |
| Batch 4 — Observability | ✅ PASS | 2026-03-30 (Prometheus/Loki config fix) |
| Batch 5 — Recovery + Docs | ✅ PASS | 2026-03-30 |
| Batch 6 — Go/No-Go | ✅ GO | 2026-03-30 |

**Entregáveis operacionais**: compose unificado com profiles, integration test suite (scenarios + chaos + performance), CI/CD pipelines, release workflow, cross-platform packaging.

---

## cerebro (RAG Retrieval)

**Última atividade**: 2026-04-23 (public launch hardening, i18n docs)

| Status | Área |
|--------|------|
| ✅ | RAG pipeline (ingest, query, rerank) |
| ✅ | Multi-backend (pgvector, qdrant, Azure Search, OpenSearch) |
| ✅ | Dashboard UI (backend selector, content hash dedup) |
| ✅ | CLI completo + TUI |
| ✅ | Public launch hardening |
| 🔄 | Agentic GPT roadmap (ver `docs/project/AGENTIC_GPT_ROADMAP.md`) |

**Consome**: `knowledge_base.json` do adr-ledger para RAG sobre decisões arquiteturais.

---

## securellm-mcp (MCP Tools Backend)

**Última atividade**: 2026-04-19 (cachix → marcosfpina, sops/age no devShell)

| Status | Área |
|--------|------|
| ✅ | 80+ MCP tools operacionais |
| ✅ | TypeScript type safety (refactor 2026-04-15) |
| ✅ | CI: format check (prettier), cachix cache |
| 🔄 | sops/age integração no devShell |

**Dependência crítica**: adr-ledger exporta `nixosModules.adr-ledger-iam` que usa `securellm-mcp` como backend de daemon.

---

## spider-nix (NixOS Build Tooling)

**Última atividade**: 2026-04-17 (nodejs 22 → 24, spider CLI wrapper)

| Status | Área |
|--------|------|
| ✅ | CLI wrapper funcional |
| ✅ | nodejs 24 |
| ✅ | flake inputs atualizados |

**Usado como**: input transitivo no flake do adr-ledger. Deve permanecer remoto (não `file://`).

---

## Dependências Críticas entre Projetos

| Consumidor | Depende de | Tipo |
|------------|-----------|------|
| neotron (OPA eval) | adr-ledger (policy bundle) | runtime |
| adr-ledger (daemon) | securellm-mcp | systemd ExecStart |
| adr-ledger (build) | spider-nix | flake input |
| sentinel (events) | spectre (NATS bus) | infra |
| phantom (SOC) | spectre (event bus) | infra |
| cerebro (RAG) | adr-ledger (knowledge_base.json) | data |
| neotron (NATS events) | spectre (bus) | infra |

---

## Blocos de Trabalho Ativos (2026-04-26)

### P0 — Pré-release público (adr-ledger)
1. Smoke test enforcement layer: deny de ação fora de `allowedActions` confirmado
2. `nixosModules.adr-ledger-iam` exportado e documentado no README
3. CI workflow corrigido para entrypoints atuais
4. GitHub Release criado (tag + changelog + known issues)

### P1 — neotron
5. SYNAPSE: conectar embedding pipeline ao pgvector
6. `api_secret_key` via SOPS → habilitar auth JWT real
7. Implementar testes reais em `test_specialized.py`, `test_providers.py`

### P2 — spectre
8. Infraestrutura observability: Jaeger + Prometheus + Grafana no compose
9. `/metrics` endpoint no `spectre-proxy`

### P3 — phantom
10. Frontend sub-components e test infra (Vitest + Playwright)
11. IntelAgent crates restantes (security, governance, memory)

---

## Como Manter Este Arquivo

Atualizar após cada sessão significativa de trabalho:

```bash
# 1. Atualizar status do projeto que foi trabalhado
# 2. Rodar no adr-ledger:
adr sync
git add PROJECT_STATUS.md knowledge/
git commit -m "chore(status): sync ecosystem project status"
```

Campos que mudam com frequência: **rating**, **última atividade**, **gaps críticos**, **blocos de trabalho ativos**.  
Campos estáveis: mapa de dependências, fases concluídas.
