"""Tests for ATS keyword analysis and resume generation in the Writer Sandbox."""

from pathlib import Path

import pytest

from phantom.providers.base import AIProvider, GenerationResult, ProviderStatus
from phantom.writer import WriterLLM, WriterService
from phantom.writer.ats import ats_friendliness_warnings, extract_keywords, score_keywords


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


def test_extract_keywords_finds_significant_terms():
    job_description = (
        "We need a Python engineer with AWS experience and machine learning "
        "background. Machine learning skills and AWS knowledge are required."
    )

    keywords = extract_keywords(job_description, top_n=10)

    assert "AWS" in keywords
    assert any(k.lower() == "machine learning" for k in keywords)
    assert "Python" in keywords


def test_extract_keywords_deduplicates_case_insensitively():
    text = "Docker docker DOCKER container orchestration"

    keywords = extract_keywords(text, top_n=10)

    assert sum(1 for k in keywords if k.lower() == "docker") == 1


def test_score_keywords_splits_found_and_missing():
    resume = "Experience with Python and Docker in production."
    keywords = ["Python", "Docker", "Kubernetes"]

    found, missing = score_keywords(resume, keywords)

    assert found == ["Python", "Docker"]
    assert missing == ["Kubernetes"]


def test_ats_friendliness_warnings_flags_missing_email_and_headings():
    resume = "Just a wall of prose with no structure and no contact info."

    warnings = ats_friendliness_warnings(resume)

    assert any("email" in w.lower() for w in warnings)
    assert any("heading" in w.lower() for w in warnings)
    assert any("bullet" in w.lower() for w in warnings)


def test_ats_friendliness_warnings_flags_tables():
    resume = (
        "# Resume\n\ncontact@example.com\n\n"
        "- Built things\n\n"
        "| Skill | Level |\n|---|---|\n| Python | Expert |\n"
    )

    warnings = ats_friendliness_warnings(resume)

    assert any("table" in w.lower() for w in warnings)


def test_ats_friendliness_warnings_clean_resume_has_none():
    resume = "# Jane Doe\n\njane@example.com\n\n## Experience\n\n- Built ATS-friendly resumes\n"

    warnings = ats_friendliness_warnings(resume)

    assert warnings == []


def test_writer_score_ats_via_service(tmp_path: Path):
    service = WriterService(tmp_path / "writer")
    workspace = service.create_workspace("Job Search")
    draft = service.create_draft(
        workspace.id,
        title="Resume",
        markdown="# Jane Doe\n\njane@example.com\n\n## Skills\n\n- Python\n- Docker\n",
    )

    score = service.score_ats(
        workspace.id,
        draft.id,
        job_description="Looking for a Python engineer with Docker and Kubernetes skills.",
    )

    assert "Python" in score.keywords_found
    assert "Docker" in score.keywords_found
    assert "Kubernetes" in score.keywords_missing
    assert 0.0 < score.coverage < 1.0


def test_generate_resume_requires_available_provider(tmp_path: Path):
    service = WriterService(
        tmp_path / "writer", llm=WriterLLM(provider=FakeLocalProvider(available=False))
    )
    workspace = service.create_workspace("Job Search")
    dump = service.create_dump(
        workspace.id,
        raw_markdown="Trabalhei 5 anos com Python e AWS em projetos de dados.",
    )

    with pytest.raises(RuntimeError, match="Local LLM"):
        service.generate_resume(workspace.id, dump.id, job_description="Python + AWS role")


def test_generate_resume_weaves_keywords_into_prompt(tmp_path: Path):
    provider = FakeLocalProvider(response="# Resume\n\njane@example.com\n\n- Python\n- AWS\n")
    service = WriterService(tmp_path / "writer", llm=WriterLLM(provider=provider))
    workspace = service.create_workspace("Job Search")
    dump = service.create_dump(
        workspace.id,
        raw_markdown="Trabalhei 5 anos com Python e AWS em projetos de dados.",
    )

    draft = service.generate_resume(
        workspace.id,
        dump.id,
        job_description="Senior Python engineer with AWS and Kubernetes experience.",
    )

    assert draft.markdown.startswith("# Resume")
    assert provider.prompts, "expected the local provider to receive a prompt"
    prompt = provider.prompts[0]
    assert "Python" in prompt
    assert "AWS" in prompt
    assert "resume" in prompt.lower()
