"""Filesystem-backed Writer Sandbox service."""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml

from phantom.writer._text import STOP_WORDS
from phantom.writer.llm import WriterLLM
from phantom.writer.models import (
    ATSScore,
    BrainDump,
    Distillation,
    Draft,
    DraftReview,
    PrintJobResult,
    PublishResult,
    PublishTarget,
    RelatedSource,
    WriterWorkspace,
)
from phantom.writer.print_service import PrintService


def _now() -> datetime:
    return datetime.now(UTC)


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "untitled"


def _make_id(prefix: str, title: str) -> str:
    timestamp = _now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}-{_slugify(title)[:48]}"


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _frontmatter_to_text(metadata: dict, body: str) -> str:
    serializable = {}
    for key, value in metadata.items():
        if isinstance(value, datetime):
            serializable[key] = value.isoformat()
        elif isinstance(value, Path):
            serializable[key] = str(value)
        elif isinstance(value, list):
            serializable[key] = [str(item) for item in value]
        else:
            serializable[key] = value

    frontmatter = yaml.safe_dump(
        serializable,
        allow_unicode=False,
        sort_keys=False,
    )
    return f"---\n{frontmatter}---\n\n{body.rstrip()}\n"


def _text_to_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text

    remainder = text[4:]
    if "\n---\n" not in remainder:
        return {}, text

    frontmatter_text, body = remainder.split("\n---\n", 1)
    metadata = yaml.safe_load(frontmatter_text) or {}
    return metadata, body.lstrip("\n")


class WriterService:
    """Manage local writer workspaces, dumps, drafts, and publishing."""

    def __init__(
        self,
        base_dir: Path | str = ".phantom/writer",
        llm: WriterLLM | None = None,
        printer: PrintService | None = None,
    ):
        self.base_dir = Path(base_dir)
        self._llm = llm
        self._printer = printer

    @property
    def llm(self) -> WriterLLM:
        """Local LLM assistant, created lazily. Never a cloud provider."""
        if self._llm is None:
            self._llm = WriterLLM()
        return self._llm

    @property
    def printer(self) -> PrintService:
        """Local CUPS print backend, created lazily."""
        if self._printer is None:
            self._printer = PrintService()
        return self._printer

    def create_workspace(
        self,
        name: str,
        root_path: Path | str | None = None,
        allowed_paths: list[Path | str] | None = None,
        provider: str = "local",
        network_policy: str = "offline",
    ) -> WriterWorkspace:
        workspace_id = _make_id("ws", name)
        root = Path(root_path) if root_path else self.base_dir / "workspaces" / workspace_id
        root = root.resolve()
        now = _now()
        allowed = [Path(path).resolve() for path in (allowed_paths or [root])]

        workspace = WriterWorkspace(
            id=workspace_id,
            name=name,
            root_path=root,
            allowed_paths=allowed,
            provider=provider,
            network_policy=network_policy,  # type: ignore[arg-type]
            created_at=now,
            updated_at=now,
        )
        self._write_workspace(workspace)
        return workspace

    def list_workspaces(self) -> list[WriterWorkspace]:
        workspaces_root = self.base_dir / "workspaces"
        if not workspaces_root.exists():
            return []

        workspaces = []
        for manifest in sorted(workspaces_root.glob("*/writer.toml")):
            workspaces.append(self._read_workspace(manifest))
        return workspaces

    def get_workspace(self, workspace_id: str) -> WriterWorkspace:
        return self._read_workspace(self._workspace_root(workspace_id) / "writer.toml")

    def create_dump(
        self,
        workspace_id: str,
        raw_markdown: str,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> BrainDump:
        workspace = self.get_workspace(workspace_id)
        now = _now()
        dump_title = title or self._derive_title(raw_markdown)
        dump = BrainDump(
            id=_make_id("dump", dump_title),
            workspace_id=workspace_id,
            title=dump_title,
            raw_markdown=raw_markdown,
            tags=tags or [],
            created_at=now,
            updated_at=now,
        )

        path = workspace.root_path / "dumps" / f"{dump.id}.md"
        self._assert_within_workspace(workspace, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _frontmatter_to_text(
                {
                    "id": dump.id,
                    "workspace_id": dump.workspace_id,
                    "title": dump.title,
                    "tags": dump.tags,
                    "created_at": dump.created_at,
                    "updated_at": dump.updated_at,
                },
                dump.raw_markdown,
            ),
            encoding="utf-8",
        )
        return dump

    def get_dump(self, workspace_id: str, dump_id: str) -> BrainDump:
        workspace = self.get_workspace(workspace_id)
        path = workspace.root_path / "dumps" / f"{dump_id}.md"
        metadata, body = _text_to_frontmatter(path.read_text(encoding="utf-8"))
        return BrainDump(
            id=metadata["id"],
            workspace_id=metadata["workspace_id"],
            title=metadata["title"],
            raw_markdown=body,
            tags=metadata.get("tags", []),
            created_at=_parse_datetime(metadata["created_at"]),
            updated_at=_parse_datetime(metadata["updated_at"]),
        )

    def list_dumps(self, workspace_id: str) -> list[BrainDump]:
        workspace = self.get_workspace(workspace_id)
        dumps = []
        for path in sorted((workspace.root_path / "dumps").glob("*.md")):
            dumps.append(self.get_dump(workspace_id, path.stem))
        return dumps

    def distill_dump(
        self,
        workspace_id: str,
        dump_id: str,
        use_llm: bool = False,
    ) -> Distillation:
        dump = self.get_dump(workspace_id, dump_id)
        text = dump.raw_markdown.strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        summary = self._summarize(lines)
        topics = self._extract_topics(text)
        questions = [line for line in lines if line.endswith("?")]
        tasks = self._extract_tasks(lines)
        candidates = self._draft_candidates(dump.title, topics, summary)

        if use_llm:
            if not self.llm.is_available():
                raise RuntimeError("Local LLM (llama.cpp) is not available.")
            enhancement = self.llm.distill(dump.raw_markdown)
            summary = enhancement["summary"] or summary
            topics = enhancement["topics"] or topics
            candidates = enhancement["draft_candidates"] or candidates

        return Distillation(
            dump_id=dump.id,
            summary=summary,
            topics=topics,
            questions=questions[:10],
            tasks=tasks[:10],
            draft_candidates=candidates,
            related_sources=self._related_sources(workspace_id, dump.id, topics),
        )

    def create_draft(
        self,
        workspace_id: str,
        title: str,
        markdown: str,
        frontmatter: dict | None = None,
        source_dump_ids: list[str] | None = None,
    ) -> Draft:
        workspace = self.get_workspace(workspace_id)
        now = _now()
        draft = Draft(
            id=_make_id("draft", title),
            workspace_id=workspace_id,
            title=title,
            markdown=markdown,
            frontmatter=frontmatter or self._default_frontmatter(title),
            source_dump_ids=source_dump_ids or [],
            created_at=now,
            updated_at=now,
        )
        self._write_draft(workspace, draft)
        return draft

    def update_draft(
        self,
        workspace_id: str,
        draft_id: str,
        markdown: str,
        title: str | None = None,
        frontmatter: dict | None = None,
    ) -> Draft:
        draft = self.get_draft(workspace_id, draft_id)
        workspace = self.get_workspace(workspace_id)
        draft.markdown = markdown
        draft.title = title or draft.title
        if frontmatter is not None:
            draft.frontmatter = frontmatter
        draft.updated_at = _now()
        self._write_draft(workspace, draft)
        return draft

    def generate_draft(
        self,
        workspace_id: str,
        dump_id: str,
        instruction: str | None = None,
    ) -> Draft:
        """Generate a starter draft from a dump using the local LLM."""
        if not self.llm.is_available():
            raise RuntimeError("Local LLM (llama.cpp) is not available.")

        dump = self.get_dump(workspace_id, dump_id)
        distillation = self.distill_dump(workspace_id, dump_id)
        title = (
            distillation.draft_candidates[0] if distillation.draft_candidates else dump.title
        )
        markdown = self.llm.draft(
            title=title,
            summary=distillation.summary,
            topics=distillation.topics,
            raw_markdown=dump.raw_markdown,
            instruction=instruction,
        )
        return self.create_draft(
            workspace_id,
            title=title,
            markdown=markdown,
            source_dump_ids=[dump.id],
        )

    def score_ats(
        self,
        workspace_id: str,
        draft_id: str,
        job_description: str,
        top_n: int = 20,
    ) -> ATSScore:
        """Score a resume draft's ATS keyword coverage against a job description."""
        from phantom.writer.ats import (
            ats_friendliness_warnings,
            extract_keywords,
            score_keywords,
        )

        draft = self.get_draft(workspace_id, draft_id)
        keywords = extract_keywords(job_description, top_n=top_n)
        found, missing = score_keywords(draft.markdown, keywords)
        coverage = len(found) / len(keywords) if keywords else 0.0

        return ATSScore(
            draft_id=draft.id,
            keywords=keywords,
            keywords_found=found,
            keywords_missing=missing,
            coverage=round(coverage, 3),
            warnings=ats_friendliness_warnings(draft.markdown),
        )

    def generate_resume(
        self,
        workspace_id: str,
        dump_id: str,
        job_description: str,
        instruction: str | None = None,
    ) -> Draft:
        """Generate a starter resume draft tailored to a job description's ATS keywords."""
        if not self.llm.is_available():
            raise RuntimeError("Local LLM (llama.cpp) is not available.")

        from phantom.writer.ats import extract_keywords

        dump = self.get_dump(workspace_id, dump_id)
        keywords = extract_keywords(job_description, top_n=20)
        guidance = (
            f"{instruction.strip() + ' ' if instruction else ''}"
            "Write this as a resume/CV in Markdown with clear section headings "
            "(Summary, Experience, Skills, Education) and bullet points, not "
            "prose paragraphs. Only include truthful content grounded in the "
            "source material below; naturally work in these ATS keywords where "
            f"they genuinely apply: {', '.join(keywords)}."
        )
        markdown = self.llm.draft(
            title=dump.title,
            summary="",
            topics=keywords,
            raw_markdown=dump.raw_markdown,
            instruction=guidance,
        )
        return self.create_draft(
            workspace_id,
            title=dump.title,
            markdown=markdown,
            source_dump_ids=[dump.id],
        )

    def assist_draft(self, workspace_id: str, draft_id: str, instruction: str) -> Draft:
        """Revise an existing draft per instruction using the local LLM."""
        if not self.llm.is_available():
            raise RuntimeError("Local LLM (llama.cpp) is not available.")

        draft = self.get_draft(workspace_id, draft_id)
        revised = self.llm.assist(draft.markdown, instruction)
        return self.update_draft(
            workspace_id,
            draft_id,
            markdown=revised,
            title=draft.title,
            frontmatter=draft.frontmatter,
        )

    def get_draft(self, workspace_id: str, draft_id: str) -> Draft:
        workspace = self.get_workspace(workspace_id)
        path = workspace.root_path / "drafts" / f"{draft_id}.md"
        metadata, body = _text_to_frontmatter(path.read_text(encoding="utf-8"))
        return Draft(
            id=metadata["id"],
            workspace_id=metadata["workspace_id"],
            title=metadata["title"],
            markdown=body,
            frontmatter=metadata.get("frontmatter", {}),
            status=metadata.get("status", "draft"),
            source_dump_ids=metadata.get("source_dump_ids", []),
            created_at=_parse_datetime(metadata["created_at"]),
            updated_at=_parse_datetime(metadata["updated_at"]),
        )

    def list_drafts(self, workspace_id: str) -> list[Draft]:
        workspace = self.get_workspace(workspace_id)
        drafts = []
        for path in sorted((workspace.root_path / "drafts").glob("*.md")):
            drafts.append(self.get_draft(workspace_id, path.stem))
        return drafts

    def review_draft(self, workspace_id: str, draft_id: str) -> DraftReview:
        workspace = self.get_workspace(workspace_id)
        draft = self.get_draft(workspace_id, draft_id)

        findings = []
        try:
            import tempfile

            from phantom.pipeline.phantom_dag import ClassificationEngine

            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".md",
                encoding="utf-8",
                delete=False,
            ) as tmp:
                tmp.write(draft.markdown)
                tmp_path = Path(tmp.name)

            try:
                findings = [
                    {
                        "pattern": finding.pattern_name,
                        "count": finding.count,
                        "risk_score": finding.risk_score,
                    }
                    for finding in ClassificationEngine.scan_sensitive_content(tmp_path)
                ]
            finally:
                tmp_path.unlink(missing_ok=True)
        except Exception:
            findings = []

        required = {"title", "date", "tags", "draft"}
        missing = sorted(required - set(draft.frontmatter))
        asset_warnings = self._asset_warnings(workspace, draft.markdown)
        claim_warnings = self._claim_warnings(draft.markdown)

        return DraftReview(
            draft_id=draft.id,
            pii_or_secret_findings=findings,
            missing_frontmatter=missing,
            local_asset_warnings=asset_warnings,
            claim_warnings=claim_warnings,
            passed=not findings and not missing and not asset_warnings,
        )

    def export_draft(
        self,
        workspace_id: str,
        draft_id: str,
        output_dir: Path | str | None = None,
    ) -> PublishResult:
        workspace = self.get_workspace(workspace_id)
        draft = self.get_draft(workspace_id, draft_id)
        target_dir = Path(output_dir) if output_dir else workspace.root_path / "published"
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{_slugify(draft.title)}.md"
        output_path.write_text(
            _frontmatter_to_text(draft.frontmatter, draft.markdown),
            encoding="utf-8",
        )
        return PublishResult(
            draft_id=draft.id,
            output_path=output_path,
            message="Draft exported to Markdown.",
        )

    def print_draft(
        self,
        workspace_id: str,
        draft_id: str,
        printer: str | None = None,
    ) -> PrintJobResult:
        """Send a draft to a local printer, pseudonymized while in transit."""
        draft = self.get_draft(workspace_id, draft_id)
        result = self.printer.print_markdown(draft.markdown, printer=printer)
        return PrintJobResult(
            draft_id=draft.id,
            printer=result.printer,
            pseudonym_count=result.pseudonym_count,
            message=f"Draft sent to local printer via {result.backend}.",
        )

    def publish_git(
        self,
        workspace_id: str,
        draft_id: str,
        target: PublishTarget,
        commit: bool = True,
    ) -> PublishResult:
        review = self.review_draft(workspace_id, draft_id)
        if not review.passed:
            return PublishResult(
                draft_id=draft_id,
                output_path=target.repo_path,
                message="Publish blocked by review gate.",
            )

        draft = self.get_draft(workspace_id, draft_id)
        repo = target.repo_path.resolve()
        content_dir = repo / target.content_dir
        content_dir.mkdir(parents=True, exist_ok=True)
        output_path = content_dir / f"{_slugify(draft.title)}.md"
        output_path.write_text(
            _frontmatter_to_text(draft.frontmatter, draft.markdown),
            encoding="utf-8",
        )

        if not commit:
            return PublishResult(
                draft_id=draft.id,
                output_path=output_path,
                committed=False,
                message="Draft written to Git working tree.",
            )

        subprocess.run(["git", "add", str(output_path)], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"docs: publish {draft.title}"],
            cwd=repo,
            check=True,
        )
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            text=True,
        ).strip()
        return PublishResult(
            draft_id=draft.id,
            output_path=output_path,
            committed=True,
            commit_sha=commit_sha,
            message="Draft published to Git working tree.",
        )

    def _workspace_root(self, workspace_id: str) -> Path:
        return self.base_dir / "workspaces" / workspace_id

    def _write_workspace(self, workspace: WriterWorkspace) -> None:
        workspace.root_path.mkdir(parents=True, exist_ok=True)
        for dirname in ("dumps", "drafts", "published", "assets", "index"):
            (workspace.root_path / dirname).mkdir(parents=True, exist_ok=True)

        registry_root = self._workspace_root(workspace.id)
        registry_root.mkdir(parents=True, exist_ok=True)
        manifest = registry_root / "writer.toml"
        allowed_paths = ", ".join(f'"{path}"' for path in workspace.allowed_paths)
        manifest_text = (
            "\n".join(
                [
                    f'id = "{workspace.id}"',
                    f'name = "{workspace.name}"',
                    f'root_path = "{workspace.root_path}"',
                    f"allowed_paths = [{allowed_paths}]",
                    f'provider = "{workspace.provider}"',
                    f'network_policy = "{workspace.network_policy}"',
                    f'created_at = "{workspace.created_at.isoformat()}"',
                    f'updated_at = "{workspace.updated_at.isoformat()}"',
                    "",
                ]
            )
        )
        manifest.write_text(
            manifest_text,
            encoding="utf-8",
        )
        (workspace.root_path / "writer.toml").write_text(
            manifest_text,
            encoding="utf-8",
        )

    def _read_workspace(self, manifest: Path) -> WriterWorkspace:
        import tomllib

        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        return WriterWorkspace(
            id=data["id"],
            name=data["name"],
            root_path=Path(data["root_path"]),
            allowed_paths=[Path(path) for path in data.get("allowed_paths", [])],
            provider=data.get("provider", "local"),
            network_policy=data.get("network_policy", "offline"),
            created_at=_parse_datetime(data["created_at"]),
            updated_at=_parse_datetime(data["updated_at"]),
        )

    def _assert_within_workspace(self, workspace: WriterWorkspace, path: Path) -> None:
        resolved = path.resolve()
        root = workspace.root_path.resolve()
        if root != resolved and root not in resolved.parents:
            raise ValueError(f"Path escapes writer workspace: {path}")

    def _write_draft(self, workspace: WriterWorkspace, draft: Draft) -> None:
        path = workspace.root_path / "drafts" / f"{draft.id}.md"
        self._assert_within_workspace(workspace, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _frontmatter_to_text(
                {
                    "id": draft.id,
                    "workspace_id": draft.workspace_id,
                    "title": draft.title,
                    "frontmatter": draft.frontmatter,
                    "status": draft.status,
                    "source_dump_ids": draft.source_dump_ids,
                    "created_at": draft.created_at,
                    "updated_at": draft.updated_at,
                },
                draft.markdown,
            ),
            encoding="utf-8",
        )

    def _derive_title(self, markdown: str) -> str:
        for line in markdown.splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                return line[:80]
        return "Untitled Dump"

    def _default_frontmatter(self, title: str) -> dict:
        return {
            "title": title,
            "date": _now().date().isoformat(),
            "tags": [],
            "draft": True,
        }

    def _summarize(self, lines: list[str]) -> str:
        if not lines:
            return ""
        summary = " ".join(lines[:3])
        return summary[:500]

    def _extract_topics(self, text: str) -> list[str]:
        words = re.findall(r"[A-Za-zÀ-ÿ0-9_]{4,}", text.lower())
        counts = Counter(word for word in words if word not in STOP_WORDS)
        return [word for word, _ in counts.most_common(8)]

    def _extract_tasks(self, lines: list[str]) -> list[str]:
        tasks = []
        for line in lines:
            lowered = line.lower()
            if (
                lowered.startswith(("- [ ]", "todo", "fazer", "preciso"))
                or " precisa " in lowered
            ):
                tasks.append(line)
        return tasks

    def _draft_candidates(self, title: str, topics: list[str], summary: str) -> list[str]:
        candidates = [title]
        if topics:
            candidates.append(f"Notas sobre {', '.join(topics[:3])}")
        if summary:
            candidates.append(f"Como transformar este dump: {summary[:80]}")
        return candidates[:3]

    def _related_sources(
        self,
        workspace_id: str,
        current_dump_id: str,
        topics: list[str],
    ) -> list[RelatedSource]:
        if not topics:
            return []

        sources = []
        topic_set = set(topics)
        for dump in self.list_dumps(workspace_id):
            if dump.id == current_dump_id:
                continue
            other_topics = set(self._extract_topics(dump.raw_markdown))
            overlap = topic_set & other_topics
            if overlap:
                sources.append(
                    RelatedSource(
                        text=dump.raw_markdown[:500],
                        score=len(overlap) / max(len(topic_set), 1),
                        metadata={"dump_id": dump.id, "title": dump.title},
                    )
                )
        return sorted(sources, key=lambda source: source.score, reverse=True)[:5]

    def _asset_warnings(self, workspace: WriterWorkspace, markdown: str) -> list[str]:
        warnings = []
        for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", markdown):
            target = match.group(1)
            if re.match(r"^[a-z]+://", target):
                continue
            asset_path = (workspace.root_path / target).resolve()
            if not asset_path.exists():
                warnings.append(f"Missing local asset: {target}")
        return warnings

    def _claim_warnings(self, markdown: str) -> list[str]:
        warnings = []
        for line in markdown.splitlines():
            has_number = bool(re.search(r"\d+[%x]?", line))
            has_source = "http://" in line or "https://" in line or "[^" in line
            if has_number and not has_source:
                warnings.append(f"Numeric claim without source: {line[:120]}")
        return warnings[:10]
