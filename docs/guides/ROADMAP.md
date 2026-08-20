# Phantom Roadmap

## Active Direction

Phantom is expanding from local-first document intelligence into a confined
writing environment:

> A safe place to think messily, write clearly, retrieve private context, and
> publish Markdown without leaking workspace data by default.

The active desktop direction is **GTK4/libadwaita**. The previous
Tauri/Svelte Cortex Desktop remains in the repository as legacy code during the
migration, but new product work should target `apps/desktop/`.

## Shipped / Current

- [x] Python package layout under `src/phantom/`
- [x] FastAPI service with health, metrics, vector, chat, prompt, and pipeline endpoints
- [x] CLI for extraction, classification, scanning, RAG, and utility tools
- [x] CORTEX chunking, embeddings, and insight extraction
- [x] FAISS/BM25 hybrid retrieval
- [x] DAG classification, sanitization, quarantine, and reports
- [x] Local-first LlamaCpp provider path
- [x] Nix development shell
- [x] Writer Sandbox service with Markdown-backed workspaces, dumps, drafts, review, export, and Git publishing
- [x] Writer API under `/api/writer/*`
- [x] Initial GTK4 Writer Desktop shell

## In Progress

- [ ] Bring Python lint/test baseline back to green with unmasked checks
- [ ] Expand GTK4 Writer UX beyond the initial dump/distill/write/export shell
- [ ] Add focused tests for Writer API, filesystem storage, and publish gates
- [ ] Update docs that still describe Tauri as the primary desktop surface
- [ ] Harden API security defaults before any network-exposed deployment

## Near Term

- [ ] Writer workspace selector and explicit allowed-path management
- [ ] Draft review UI for secrets/PII, missing frontmatter, assets, and claims
- [ ] RAG-backed related-source panel constrained by workspace policy
- [ ] Static-blog export presets for Hugo, Astro, and Jekyll
- [ ] Git-over-SSH remote publish adapter with explicit confirmation
- [ ] Autosave/version history for dumps and drafts

## Long Term

- [ ] Rsync/SFTP publish adapter
- [ ] WordPress/Ghost adapters
- [ ] Voice/audio dump capture
- [ ] Offline model management from the desktop app
- [ ] NixOS module for system-level deployment
- [ ] Distributed/multi-node processing only after local sandbox semantics are stable

## Legacy

- `cortex-desktop/` is the legacy Tauri/Svelte desktop implementation.
- Active commands use `phantom-desktop`; legacy commands should be explicitly
  named with `legacy`.
- New desktop features should not be added to Tauri unless they are needed to
  preserve migration compatibility.

---

*Last updated: 2026-07-22*
