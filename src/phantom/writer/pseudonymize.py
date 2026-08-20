"""Reversible pseudonymization for Writer Sandbox print payloads.

Reuses the same sensitive-content patterns already applied in
``WriterService.review_draft`` (via ``ClassificationEngine``) so detection
stays consistent between the review gate and the print pipeline.
"""

from __future__ import annotations

import re


def pseudonymize(text: str) -> tuple[str, dict[str, str]]:
    """Replace detected PII/secrets with stable placeholders.

    Returns the pseudonymized text and a mapping of placeholder -> original
    value. The mapping is the only way to recover the original text; treat it
    as sensitive as the text itself.
    """
    from phantom.pipeline.phantom_dag import ClassificationEngine

    mapping: dict[str, str] = {}
    reverse: dict[str, str] = {}
    counters: dict[str, int] = {}

    def _replace(pattern_name: str, match: re.Match) -> str:
        original = match.group(0)
        if original in reverse:
            return reverse[original]
        counters[pattern_name] = counters.get(pattern_name, 0) + 1
        placeholder = f"[[REDACTED:{pattern_name.upper()}:{counters[pattern_name]}]]"
        mapping[placeholder] = original
        reverse[original] = placeholder
        return placeholder

    pseudonymized = text
    for pattern, pattern_name, _risk in ClassificationEngine.SENSITIVE_PATTERNS:
        pseudonymized = re.sub(
            pattern,
            lambda m, name=pattern_name: _replace(name, m),
            pseudonymized,
            flags=re.IGNORECASE,
        )
    return pseudonymized, mapping


def depseudonymize(text: str, mapping: dict[str, str]) -> str:
    """Restore original values from pseudonymized text + its mapping."""
    restored = text
    for placeholder, original in mapping.items():
        restored = restored.replace(placeholder, original)
    return restored
