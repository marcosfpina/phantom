"""FastAPI router for the Writer Sandbox."""

import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from phantom.writer.models import PublishTarget
from phantom.writer.service import WriterService

router = APIRouter(prefix="/api/writer", tags=["writer"])


def get_writer_service() -> WriterService:
    """Return the default filesystem-backed writer service."""
    import os

    return WriterService(os.environ.get("PHANTOM_WRITER_HOME", ".phantom/writer"))


class CreateWorkspaceRequest(BaseModel):
    name: str
    root_path: str | None = None
    allowed_paths: list[str] | None = None
    provider: str = "local"
    network_policy: str = "offline"


class CreateDumpRequest(BaseModel):
    workspace_id: str
    raw_markdown: str
    title: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreateDraftRequest(BaseModel):
    workspace_id: str
    title: str
    markdown: str
    frontmatter: dict | None = None
    source_dump_ids: list[str] = Field(default_factory=list)


class UpdateDraftRequest(BaseModel):
    workspace_id: str
    markdown: str
    title: str | None = None
    frontmatter: dict | None = None


class ExportDraftRequest(BaseModel):
    workspace_id: str
    output_dir: str | None = None


class PrintDraftRequest(BaseModel):
    workspace_id: str
    printer: str | None = None


class ScoreATSRequest(BaseModel):
    workspace_id: str
    job_description: str
    top_n: int = 20


class GenerateResumeRequest(BaseModel):
    workspace_id: str
    job_description: str
    instruction: str | None = None


class PublishGitRequest(BaseModel):
    workspace_id: str
    draft_id: str
    target: PublishTarget
    commit: bool = True


@router.post("/workspaces")
async def create_workspace(request: CreateWorkspaceRequest):
    """Create a confined writer workspace."""
    try:
        service = get_writer_service()
        return service.create_workspace(
            name=request.name,
            root_path=request.root_path,
            allowed_paths=request.allowed_paths,
            provider=request.provider,
            network_policy=request.network_policy,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workspaces")
async def list_workspaces():
    """List known writer workspaces."""
    return get_writer_service().list_workspaces()


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str):
    """Read a writer workspace manifest."""
    try:
        return get_writer_service().get_workspace(workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc


@router.get("/workspaces/{workspace_id}/dumps")
async def list_dumps(workspace_id: str):
    """List brain dumps for a workspace."""
    try:
        return get_writer_service().list_dumps(workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc


@router.get("/workspaces/{workspace_id}/drafts")
async def list_drafts(workspace_id: str):
    """List drafts for a workspace."""
    try:
        return get_writer_service().list_drafts(workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc


@router.post("/dumps")
async def create_dump(request: CreateDumpRequest):
    """Capture an unstructured brain dump."""
    try:
        return get_writer_service().create_dump(
            workspace_id=request.workspace_id,
            raw_markdown=request.raw_markdown,
            title=request.title,
            tags=request.tags,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/dumps/{dump_id}")
async def get_dump(
    dump_id: str,
    workspace_id: str = Query(..., description="Workspace that owns the dump"),
):
    """Read a brain dump by id."""
    try:
        return get_writer_service().get_dump(workspace_id, dump_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dump not found") from exc


@router.post("/dumps/{dump_id}/distill")
async def distill_dump(
    dump_id: str,
    workspace_id: str = Query(..., description="Workspace that owns the dump"),
    use_llm: bool = Query(False, description="Enhance distillation with the local LLM"),
):
    """Derive summary, topics, tasks, questions, and draft candidates."""
    try:
        return get_writer_service().distill_dump(workspace_id, dump_id, use_llm=use_llm)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dump not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class GenerateDraftRequest(BaseModel):
    workspace_id: str
    instruction: str | None = None


class AssistDraftRequest(BaseModel):
    workspace_id: str
    instruction: str


@router.post("/dumps/{dump_id}/draft")
async def generate_draft(dump_id: str, request: GenerateDraftRequest):
    """Generate a starter Markdown draft from a dump using the local LLM."""
    try:
        return get_writer_service().generate_draft(
            workspace_id=request.workspace_id,
            dump_id=dump_id,
            instruction=request.instruction,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dump not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/assist")
async def assist_draft(draft_id: str, request: AssistDraftRequest):
    """Revise an existing draft per instruction using the local LLM."""
    try:
        return get_writer_service().assist_draft(
            workspace_id=request.workspace_id,
            draft_id=draft_id,
            instruction=request.instruction,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Draft not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/drafts")
async def create_draft(request: CreateDraftRequest):
    """Create a focused Markdown draft."""
    try:
        return get_writer_service().create_draft(
            workspace_id=request.workspace_id,
            title=request.title,
            markdown=request.markdown,
            frontmatter=request.frontmatter,
            source_dump_ids=request.source_dump_ids,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, request: UpdateDraftRequest):
    """Update a focused Markdown draft."""
    try:
        return get_writer_service().update_draft(
            workspace_id=request.workspace_id,
            draft_id=draft_id,
            markdown=request.markdown,
            title=request.title,
            frontmatter=request.frontmatter,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Draft not found") from exc


@router.post("/drafts/{draft_id}/review")
async def review_draft(
    draft_id: str,
    workspace_id: str = Query(..., description="Workspace that owns the draft"),
):
    """Run pre-publication review gates for a draft."""
    try:
        return get_writer_service().review_draft(workspace_id, draft_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Draft not found") from exc


@router.post("/drafts/{draft_id}/export")
async def export_draft(draft_id: str, request: ExportDraftRequest):
    """Export a draft to Markdown."""
    try:
        output_dir = Path(request.output_dir) if request.output_dir else None
        return get_writer_service().export_draft(
            workspace_id=request.workspace_id,
            draft_id=draft_id,
            output_dir=output_dir,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Draft not found") from exc


@router.post("/drafts/{draft_id}/print")
async def print_draft(draft_id: str, request: PrintDraftRequest):
    """Send a draft to a local printer, pseudonymized while in transit."""
    try:
        return get_writer_service().print_draft(
            workspace_id=request.workspace_id,
            draft_id=draft_id,
            printer=request.printer,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Draft not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/ats-score")
async def score_ats(draft_id: str, request: ScoreATSRequest):
    """Score a resume draft's ATS keyword coverage against a job description."""
    try:
        return get_writer_service().score_ats(
            workspace_id=request.workspace_id,
            draft_id=draft_id,
            job_description=request.job_description,
            top_n=request.top_n,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Draft not found") from exc


@router.post("/dumps/{dump_id}/resume")
async def generate_resume(dump_id: str, request: GenerateResumeRequest):
    """Generate a starter resume draft tailored to a job description, via the local LLM."""
    try:
        return get_writer_service().generate_resume(
            workspace_id=request.workspace_id,
            dump_id=dump_id,
            job_description=request.job_description,
            instruction=request.instruction,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dump not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/publish/git")
async def publish_git(request: PublishGitRequest):
    """Publish a reviewed draft into a Git/static-blog working tree."""
    try:
        return get_writer_service().publish_git(
            workspace_id=request.workspace_id,
            draft_id=request.draft_id,
            target=request.target,
            commit=request.commit,
        )
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Draft or target not found") from exc
