"""Local-only LLM assistance for the Writer Sandbox.

The writer product model is local-first: dumps and drafts never leave the
workspace unless the user explicitly publishes. Assistance follows the same
rule -- the only backing provider here is a local llama.cpp server. There is
no cloud provider path in this module by design.
"""

from __future__ import annotations

from phantom.providers.base import AIProvider
from phantom.providers.llamacpp import LlamaCppProvider


class WriterLLM:
    """Local LLM assistance for distillation, drafting, and revision."""

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or LlamaCppProvider()

    def is_available(self) -> bool:
        return self.provider.is_available()

    def distill(self, raw_markdown: str, *, max_tokens: int = 400) -> dict:
        """Ask the local LLM for a summary, topics, and draft title ideas."""
        prompt = (
            "You are a careful editor distilling a raw brain dump into structure. "
            "Ground everything in the dump; do not invent facts. Reply with exactly "
            "these three labeled lines and nothing else:\n"
            "SUMMARY: <2-3 sentence summary>\n"
            "TOPICS: <comma-separated topics, lowercase, no more than 8>\n"
            "DRAFT_IDEAS: <up to 3 candidate titles, separated by |>\n\n"
            f"DUMP:\n{raw_markdown.strip()}\n"
        )
        result = self.provider.generate(prompt, max_tokens=max_tokens, temperature=0.3)
        return self._parse_distill(result.text)

    def draft(
        self,
        title: str,
        summary: str,
        topics: list[str],
        raw_markdown: str,
        instruction: str | None = None,
        *,
        max_tokens: int = 800,
    ) -> str:
        """Generate a starter Markdown draft from a dump and its distillation."""
        guidance = instruction or "Write a focused, well-structured Markdown draft."
        prompt = (
            "You are a writing assistant turning a raw brain dump into a clean "
            "Markdown draft. Keep every claim grounded in the source material; do "
            "not invent facts, numbers, or sources.\n\n"
            f"TITLE: {title}\n"
            f"SUMMARY: {summary}\n"
            f"TOPICS: {', '.join(topics)}\n"
            f"INSTRUCTION: {guidance}\n\n"
            f"SOURCE MATERIAL:\n{raw_markdown.strip()}\n\n"
            "Write the Markdown draft now, starting with a level-1 heading:\n"
        )
        result = self.provider.generate(prompt, max_tokens=max_tokens, temperature=0.4)
        return result.text.strip()

    def assist(self, markdown: str, instruction: str, *, max_tokens: int = 800) -> str:
        """Revise an existing draft per a free-form instruction."""
        prompt = (
            "You are a writing assistant revising a Markdown draft. Preserve "
            "factual content and existing sources; do not add unsupported claims. "
            "Return only the revised Markdown draft, nothing else.\n\n"
            f"INSTRUCTION: {instruction}\n\n"
            f"DRAFT:\n{markdown.strip()}\n"
        )
        result = self.provider.generate(prompt, max_tokens=max_tokens, temperature=0.4)
        return result.text.strip()

    def _parse_distill(self, text: str) -> dict:
        summary = ""
        topics: list[str] = []
        draft_candidates: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            upper = line.upper()
            if upper.startswith("SUMMARY:"):
                summary = line.split(":", 1)[1].strip()
            elif upper.startswith("TOPICS:"):
                topics = [t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()]
            elif upper.startswith("DRAFT_IDEAS:"):
                draft_candidates = [
                    d.strip() for d in line.split(":", 1)[1].split("|") if d.strip()
                ]
        return {"summary": summary, "topics": topics, "draft_candidates": draft_candidates}
