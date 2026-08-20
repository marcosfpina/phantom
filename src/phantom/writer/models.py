"""Data models for the Phantom Writer Sandbox."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

NetworkPolicy = Literal["offline", "git_only", "online"]
DraftStatus = Literal["draft", "reviewed", "published"]
PublishType = Literal["git"]


class WriterWorkspace(BaseModel):
    """A confined writing workspace with explicit local boundaries."""

    id: str
    name: str
    root_path: Path
    allowed_paths: list[Path] = Field(default_factory=list)
    provider: str = "local"
    network_policy: NetworkPolicy = "offline"
    created_at: datetime
    updated_at: datetime


class BrainDump(BaseModel):
    """Raw thought capture. This content is never mutated by distillation."""

    id: str
    workspace_id: str
    title: str
    raw_markdown: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RelatedSource(BaseModel):
    """A source snippet linked to a distillation or draft."""

    text: str
    score: float = 0.0
    metadata: dict = Field(default_factory=dict)


class Distillation(BaseModel):
    """Structured material derived from a brain dump."""

    dump_id: str
    summary: str
    topics: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    draft_candidates: list[str] = Field(default_factory=list)
    related_sources: list[RelatedSource] = Field(default_factory=list)


class Draft(BaseModel):
    """Focused Markdown draft derived from dumps or direct writing."""

    id: str
    workspace_id: str
    title: str
    markdown: str
    frontmatter: dict = Field(default_factory=dict)
    status: DraftStatus = "draft"
    source_dump_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DraftReview(BaseModel):
    """Pre-publication review result."""

    draft_id: str
    pii_or_secret_findings: list[dict] = Field(default_factory=list)
    missing_frontmatter: list[str] = Field(default_factory=list)
    local_asset_warnings: list[str] = Field(default_factory=list)
    claim_warnings: list[str] = Field(default_factory=list)
    passed: bool = False


class PublishTarget(BaseModel):
    """Git/static-site publishing target."""

    type: PublishType = "git"
    repo_path: Path
    remote: str = "origin"
    branch: str = "main"
    content_dir: Path = Path("content")


class PublishResult(BaseModel):
    """Result of exporting or publishing a draft."""

    draft_id: str
    output_path: Path
    committed: bool = False
    commit_sha: str | None = None
    message: str


class PrintJobResult(BaseModel):
    """Result of a local, pseudonymized print job."""

    draft_id: str
    printer: str | None = None
    pseudonym_count: int = 0
    message: str


class ATSScore(BaseModel):
    """Keyword coverage of a resume draft against a job description."""

    draft_id: str
    keywords: list[str] = Field(default_factory=list)
    keywords_found: list[str] = Field(default_factory=list)
    keywords_missing: list[str] = Field(default_factory=list)
    coverage: float = 0.0
    warnings: list[str] = Field(default_factory=list)
