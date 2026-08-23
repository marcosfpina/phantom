"""Tests for the filesystem-backed Writer Sandbox."""

from pathlib import Path

import pytest

from phantom.providers.base import AIProvider, GenerationResult, ProviderStatus
from phantom.writer import PrintService, WriterLLM, WriterService
from phantom.writer.models import PublishTarget
from phantom.writer.print_service import PrintEnvelope
from phantom.writer.pseudonymize import depseudonymize, pseudonymize


class FakeLocalProvider(AIProvider):
    """Stand-in for a local llama.cpp server, never a cloud provider."""

    def __init__(self, response: str = "", available: bool = True):
        super().__init__()
        self.response = response
        self.available = available
        self.prompts: list[str] = []

    @property
    def name(self) -> str:
        return "fake-local"

    def is_available(self) -> bool:
        self._status = ProviderStatus.AVAILABLE if self.available else ProviderStatus.UNAVAILABLE
        return self.available

    def generate(self, prompt: str, max_tokens=None, temperature=None, **kwargs):
        self.prompts.append(prompt)
        return GenerationResult(text=self.response, model="fake-local")


def test_writer_dump_distill_draft_export(tmp_path: Path):
    service = WriterService(tmp_path / "writer")
    workspace = service.create_workspace("Writing Lab")

    dump = service.create_dump(
        workspace.id,
        raw_markdown=(
            "Preciso fazer um brain dump sobre escrita segura.\n"
            "Como separar pensar de escrever?\n"
            "- [ ] criar um fluxo de publish via git\n"
        ),
        tags=["writer"],
    )

    loaded = service.get_dump(workspace.id, dump.id)
    assert loaded.raw_markdown == dump.raw_markdown

    distillation = service.distill_dump(workspace.id, dump.id)
    assert distillation.summary
    assert "escrita" in distillation.topics
    assert distillation.questions == ["Como separar pensar de escrever?"]
    assert "- [ ] criar um fluxo de publish via git" in distillation.tasks

    draft = service.create_draft(
        workspace.id,
        title="Escrita segura",
        markdown="# Escrita segura\n\nUm texto inicial.",
        source_dump_ids=[dump.id],
    )
    review = service.review_draft(workspace.id, draft.id)
    assert review.passed is True

    exported = service.export_draft(workspace.id, draft.id)
    assert exported.output_path.exists()
    assert exported.output_path.read_text(encoding="utf-8").startswith("---")


def test_writer_publish_git_without_commit(tmp_path: Path):
    service = WriterService(tmp_path / "writer")
    workspace = service.create_workspace("Publish Lab")
    draft = service.create_draft(
        workspace.id,
        title="Static Blog Post",
        markdown="# Static Blog Post\n\nReady to publish.",
    )

    repo = tmp_path / "blog"
    repo.mkdir()
    result = service.publish_git(
        workspace.id,
        draft.id,
        PublishTarget(repo_path=repo, content_dir=Path("content/posts")),
        commit=False,
    )

    assert result.committed is False
    assert result.output_path == repo / "content/posts/static-blog-post.md"
    assert result.output_path.exists()


def test_writer_llm_distill_parses_labeled_response():
    provider = FakeLocalProvider(
        response=(
            "SUMMARY: Notas sobre escrita segura e fluxo de publish.\n"
            "TOPICS: escrita, publish, seguranca\n"
            "DRAFT_IDEAS: Escrita segura | Fluxo de publish via git\n"
        )
    )
    llm = WriterLLM(provider=provider)

    result = llm.distill("Preciso fazer um brain dump sobre escrita segura.")

    assert result["summary"] == "Notas sobre escrita segura e fluxo de publish."
    assert result["topics"] == ["escrita", "publish", "seguranca"]
    assert result["draft_candidates"] == ["Escrita segura", "Fluxo de publish via git"]


def test_distill_dump_use_llm_requires_available_provider(tmp_path: Path):
    service = WriterService(
        tmp_path / "writer", llm=WriterLLM(provider=FakeLocalProvider(available=False))
    )
    workspace = service.create_workspace("Writing Lab")
    dump = service.create_dump(workspace.id, raw_markdown="Ideia solta sobre escrita.")

    with pytest.raises(RuntimeError, match="Local LLM"):
        service.distill_dump(workspace.id, dump.id, use_llm=True)


def test_distill_dump_use_llm_overrides_heuristics(tmp_path: Path):
    provider = FakeLocalProvider(
        response=(
            "SUMMARY: Resumo gerado localmente.\n"
            "TOPICS: escrita, ia\n"
            "DRAFT_IDEAS: Escrita assistida por IA local\n"
        )
    )
    service = WriterService(tmp_path / "writer", llm=WriterLLM(provider=provider))
    workspace = service.create_workspace("Writing Lab")
    dump = service.create_dump(workspace.id, raw_markdown="Ideia solta sobre escrita.")

    distillation = service.distill_dump(workspace.id, dump.id, use_llm=True)

    assert distillation.summary == "Resumo gerado localmente."
    assert distillation.topics == ["escrita", "ia"]
    assert distillation.draft_candidates == ["Escrita assistida por IA local"]


def test_generate_draft_creates_draft_from_llm(tmp_path: Path):
    provider = FakeLocalProvider(response="# Escrita assistida\n\nTexto gerado localmente.")
    service = WriterService(tmp_path / "writer", llm=WriterLLM(provider=provider))
    workspace = service.create_workspace("Writing Lab")
    dump = service.create_dump(workspace.id, raw_markdown="Ideia solta sobre escrita.")

    draft = service.generate_draft(workspace.id, dump.id)

    assert draft.markdown == "# Escrita assistida\n\nTexto gerado localmente."
    assert draft.source_dump_ids == [dump.id]
    assert provider.prompts, "expected the local provider to receive a prompt"


def test_generate_draft_requires_available_provider(tmp_path: Path):
    service = WriterService(
        tmp_path / "writer", llm=WriterLLM(provider=FakeLocalProvider(available=False))
    )
    workspace = service.create_workspace("Writing Lab")
    dump = service.create_dump(workspace.id, raw_markdown="Ideia solta sobre escrita.")

    with pytest.raises(RuntimeError, match="Local LLM"):
        service.generate_draft(workspace.id, dump.id)


def test_assist_draft_revises_markdown_via_llm(tmp_path: Path):
    provider = FakeLocalProvider(response="# Escrita segura\n\nVersao revisada.")
    service = WriterService(tmp_path / "writer", llm=WriterLLM(provider=provider))
    workspace = service.create_workspace("Writing Lab")
    draft = service.create_draft(
        workspace.id,
        title="Escrita segura",
        markdown="# Escrita segura\n\nRascunho inicial.",
    )

    revised = service.assist_draft(workspace.id, draft.id, "Torne mais conciso")

    assert revised.markdown == "# Escrita segura\n\nVersao revisada."
    assert revised.title == "Escrita segura"


def test_pseudonymize_roundtrip_restores_original():
    text = "Contato: marcos@example.com, CPF 123.456.789-09."

    pseudonymized, mapping = pseudonymize(text)

    assert "marcos@example.com" not in pseudonymized
    assert "123.456.789-09" not in pseudonymized
    assert mapping
    assert depseudonymize(pseudonymized, mapping) == text


def test_pseudonymize_reuses_placeholder_for_repeated_value():
    text = "Email: a@b.com. Confirme por a@b.com novamente."

    pseudonymized, mapping = pseudonymize(text)

    assert len(mapping) == 1
    assert pseudonymized.count(next(iter(mapping))) == 2


def test_print_envelope_seal_unseal_roundtrip():
    envelope = PrintEnvelope()
    sealed = envelope.seal("texto pseudonimizado", {"[[X]]": "original"})

    text, mapping = envelope.unseal(sealed)

    assert text == "texto pseudonimizado"
    assert mapping == {"[[X]]": "original"}


def test_print_service_spools_depseudonymized_text(monkeypatch):
    captured = {}

    class FakeCompletedProcess:
        returncode = 0
        stderr = b""

    def fake_run(cmd, input=None, capture_output=None, timeout=None, check=None):
        captured["cmd"] = cmd
        captured["input"] = input
        return FakeCompletedProcess()

    monkeypatch.setattr("phantom.writer.print_service.subprocess.run", fake_run)

    service = PrintService(printer="hp-deskjet-3516")
    result = service.print_markdown("Contato: marcos@example.com")

    assert result.printer == "hp-deskjet-3516"
    assert result.pseudonym_count == 1
    assert captured["cmd"] == ["lpr", "-P", "hp-deskjet-3516"]
    # The printed payload is the restored original, not the pseudonymized text.
    assert captured["input"] == b"Contato: marcos@example.com"


def test_print_service_raises_on_backend_failure(monkeypatch):
    class FakeCompletedProcess:
        returncode = 1
        stderr = b"lpr: no printer"

    def fake_run(cmd, input=None, capture_output=None, timeout=None, check=None):
        return FakeCompletedProcess()

    monkeypatch.setattr("phantom.writer.print_service.subprocess.run", fake_run)

    service = PrintService()
    with pytest.raises(RuntimeError, match="Print job failed"):
        service.print_markdown("texto qualquer")


def test_writer_print_draft_uses_printer_backend(tmp_path: Path, monkeypatch):
    captured = {}

    class FakeCompletedProcess:
        returncode = 0
        stderr = b""

    def fake_run(cmd, input=None, capture_output=None, timeout=None, check=None):
        captured["input"] = input
        return FakeCompletedProcess()

    monkeypatch.setattr("phantom.writer.print_service.subprocess.run", fake_run)

    service = WriterService(tmp_path / "writer")
    workspace = service.create_workspace("Writing Lab")
    draft = service.create_draft(
        workspace.id,
        title="Nota",
        markdown="Ligar para 11987654321 amanha.",
    )

    result = service.print_draft(workspace.id, draft.id, printer="hp-deskjet-3516")

    assert result.printer == "hp-deskjet-3516"
    assert result.pseudonym_count >= 1
    assert captured["input"].strip() == b"Ligar para 11987654321 amanha."
