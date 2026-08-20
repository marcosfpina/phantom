"""ATS (Applicant Tracking System) keyword analysis for resume drafts.

Keyword extraction and coverage scoring are purely local heuristics -- no
LLM, no network calls. Resume drafting that weaves these keywords into a
starter draft goes through the same local-only WriterLLM as the rest of the
writer module (see ``WriterService.generate_resume``).
"""

from __future__ import annotations

import re
from collections import Counter

from phantom.writer._text import STOP_WORDS

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9+.#-]{1,}")


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def extract_keywords(text: str, top_n: int = 20) -> list[str]:
    """Extract candidate ATS keywords: significant single words and bigrams.

    Favors longer words and all-caps acronyms (AWS, SQL, API) for unigrams,
    and repeated adjacent-word pairs for multi-word skills (e.g. "machine
    learning"). Counting is case-insensitive so "AWS" / "aws" collapse into
    one candidate; the first-seen casing is kept for display.
    """
    tokens = [token.rstrip(".") for token in _tokens(text)]
    tokens = [token for token in tokens if token]
    lowered = [token.lower() for token in tokens]

    counts: Counter[str] = Counter()
    display: dict[str, str] = {}

    for token, lower in zip(tokens, lowered, strict=True):
        if lower in STOP_WORDS:
            continue
        if len(token) > 3 or token.isupper():
            counts[lower] += 1
            display.setdefault(lower, token)

    for i in range(len(tokens) - 1):
        if lowered[i] in STOP_WORDS or lowered[i + 1] in STOP_WORDS:
            continue
        key = f"{lowered[i]} {lowered[i + 1]}"
        counts[key] += 1
        display.setdefault(key, f"{tokens[i]} {tokens[i + 1]}")

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [display[key] for key, _count in ranked[:top_n]]


def score_keywords(resume_text: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    """Split keywords into found vs. missing against the resume text."""
    lowered_resume = resume_text.lower()
    found = [k for k in keywords if k.lower() in lowered_resume]
    missing = [k for k in keywords if k.lower() not in lowered_resume]
    return found, missing


def ats_friendliness_warnings(resume_text: str) -> list[str]:
    """Flag common ATS-parsing hazards in a Markdown resume."""
    warnings = []

    if not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", resume_text):
        warnings.append("No email address found; ATS systems key off contact info.")

    if re.search(r"^\s*\|.*\|\s*$", resume_text, re.MULTILINE):
        warnings.append("Markdown tables detected; many ATS parsers mangle table layout.")

    if not re.search(r"^#{1,3}\s+\S", resume_text, re.MULTILINE):
        warnings.append("No section headings found; ATS parsers rely on clear section titles.")

    if not re.search(r"^\s*[-*]\s+\S", resume_text, re.MULTILINE):
        warnings.append(
            "No bullet points found; ATS-friendly resumes favor bullets over prose blocks."
        )

    return warnings
