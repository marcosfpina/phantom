# Phantom Writer Sandbox

Phantom Writer Sandbox is the local-first writing surface for capturing raw
thoughts, distilling them into structure, drafting focused Markdown, and
publishing only after explicit review.

## Product Model

Phantom separates two workflows:

- **Dump**: capture messy thinking without structure or interruption.
- **Write**: shape selected material into a clean draft.

The original dump is preserved. Distillations, drafts, reviews, and published
outputs are derived artifacts.

## Local Layout

Default storage lives under `.phantom/writer/`:

```text
.phantom/writer/
└── workspaces/
    └── <workspace_id>/
        ├── writer.toml
        ├── dumps/
        ├── drafts/
        ├── published/
        ├── assets/
        └── index/
```

Dumps and drafts are Markdown files with YAML frontmatter. Markdown remains the
human-readable source of truth; future indexes or caches are derived state.

## Desktop

Run the GTK4 desktop shell from the Nix shell:

```bash
nix develop
just desktop
```

The initial desktop supports:

- saving a brain dump;
- distilling the latest dump into summary, topics, questions, tasks, and draft ideas;
- generating a starter draft from the distillation;
- saving and exporting Markdown.

## API

The Writer API is mounted under `/api/writer`.

Useful endpoints:

```text
POST /api/writer/workspaces
GET  /api/writer/workspaces
POST /api/writer/dumps
POST /api/writer/dumps/{dump_id}/distill?workspace_id=<id>&use_llm=<bool>
POST /api/writer/dumps/{dump_id}/draft
POST /api/writer/drafts
PUT  /api/writer/drafts/{draft_id}
POST /api/writer/drafts/{draft_id}/assist
POST /api/writer/drafts/{draft_id}/review?workspace_id=<id>
POST /api/writer/drafts/{draft_id}/export
POST /api/writer/drafts/{draft_id}/print
POST /api/writer/publish/git
```

## Local LLM Assistance

Writer can optionally use a local LLM to enhance distillation, generate a
starter draft, or revise an existing draft. The only backing provider is a
local `llama.cpp` server (`LLAMACPP_URL`, default `http://localhost:8080`) --
there is no cloud provider path in the writer module.

- `distill_dump(..., use_llm=True)` — replaces the heuristic summary/topics/
  draft-candidates with LLM output; raises if the local server isn't running.
- `generate_draft(workspace_id, dump_id, instruction=None)` — asks the LLM to
  turn a dump into a starter Markdown draft.
- `assist_draft(workspace_id, draft_id, instruction)` — asks the LLM to
  revise an existing draft (e.g. "torne mais conciso").

All three fail loudly (`RuntimeError` / HTTP 503) if the local server is
unavailable, instead of silently falling back to the heuristic path.

## Local Printing

Drafts can be sent to a local printer via `print_draft` /
`POST /api/writer/drafts/{draft_id}/print`, using the system's CUPS `lpr`
(pass `printer` to target a specific CUPS queue, e.g. a wireless HP Deskjet
already configured on the host — printer discovery/setup itself is out of
scope here).

Before the draft leaves the process, it is pseudonymized using the same
`ClassificationEngine` patterns as the publish review gate (email, phone,
CPF/CNPJ, API keys, tokens, ...). The pseudonymized text and its
placeholder→original mapping are sealed in a per-job, in-memory Fernet
envelope; only immediately before handoff to `lpr` is the envelope opened and
the original text restored, so the printed page carries the real content
while the window with plaintext PII in the pipeline stays as small as
possible. The envelope key is generated per print job and never written to
disk.

## Publish Gate

Before Git publishing, Phantom runs a local review gate:

- PII/secret scanner over the draft Markdown;
- required frontmatter check: `title`, `date`, `tags`, `draft`;
- local asset existence checks;
- basic numeric-claim warning when no source marker is present.

The first publish target is a Git/static blog working tree. Remote publishing
should happen through explicit Git operations and user-controlled SSH config.
