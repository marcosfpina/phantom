"""
Unit tests for the pipeline layer.

ClassificationEngine — file-type detection via magic bytes and extensions.
SanitizationEngine  — pattern-based sensitive-data detection.
"""

import tempfile
from pathlib import Path

import pytest

from phantom.pipeline.phantom_dag import (
    Classification,
    ClassificationEngine,
    SanitizationEngine,
)

# ── ClassificationEngine ────────────────────────────────────────────

@pytest.fixture
def classifier():
    return ClassificationEngine()


class TestClassificationByMagicBytes:
    """Classify files by their magic-byte signatures."""

    def _write_tmp(self, content: bytes, suffix: str = "") -> Path:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.write(content)
        f.close()
        return Path(f.name)

    def test_png_image(self, classifier):
        path = self._write_tmp(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, ".png")
        cls, mime, _sens = classifier.classify(path)
        assert cls == Classification.IMAGES
        assert "image" in mime

    def test_pdf_document(self, classifier):
        path = self._write_tmp(b"%PDF-1.4 fake content", ".pdf")
        cls, mime, _sens = classifier.classify(path)
        assert cls == Classification.DOCUMENTS
        assert "pdf" in mime

    def test_zip_archive(self, classifier):
        path = self._write_tmp(b"PK\x03\x04" + b"\x00" * 100, ".zip")
        cls, _mime, _sens = classifier.classify(path)
        assert cls == Classification.ARCHIVES

    def test_elf_executable(self, classifier):
        path = self._write_tmp(b"\x7fELF" + b"\x00" * 100, ".elf")
        cls, _mime, _sens = classifier.classify(path)
        assert cls == Classification.EXECUTABLES

    def test_shebang_script(self, classifier):
        path = self._write_tmp(b"#!/bin/bash\necho hello\n", ".sh")
        cls, _mime, _sens = classifier.classify(path)
        assert cls == Classification.CODE

    def test_sqlite_database(self, classifier):
        path = self._write_tmp(b"SQLite format 3" + b"\x00" * 100, ".db")
        cls, _mime, _sens = classifier.classify(path)
        assert cls == Classification.DATA


class TestClassificationBySensitivity:
    """Sensitivity detection for key/config file types."""

    def _write_tmp(self, content: bytes, suffix: str) -> Path:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.write(content)
        f.close()
        return Path(f.name)

    def test_env_file_is_confidential(self, classifier):
        path = self._write_tmp(b"SECRET_KEY=abc123\n", ".env")
        _cls, _mime, sens = classifier.classify(path)
        # .env should be at least CONFIDENTIAL
        assert sens.value >= 2  # Sensitivity ordering: PUBLIC=0, INTERNAL=1, CONFIDENTIAL=2

    def test_pem_key_is_top_secret(self, classifier):
        path = self._write_tmp(
            b"-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
            ".pem",
        )
        _cls, _mime, sens = classifier.classify(path)
        assert sens.value >= 3  # TOP_SECRET


# ── SanitizationEngine ──────────────────────────────────────────────

class TestSanitizationPatterns:
    """Pattern-based sensitive-data detection in text content."""

    def test_detects_email(self):
        found = SanitizationEngine.scan_sensitive_patterns(
            "Contact us at user@example.com for details"
        )
        assert any("email" in str(f).lower() or "@" in str(f) for f in found)

    def test_detects_api_key_pattern(self):
        found = SanitizationEngine.scan_sensitive_patterns(
            "OPENAI_API_KEY=sk-abcdefghijklmnop1234567890"
        )
        # Should flag something related to keys/secrets
        assert len(found) > 0

    def test_clean_text_has_no_findings(self):
        found = SanitizationEngine.scan_sensitive_patterns(
            "The quick brown fox jumps over the lazy dog."
        )
        assert len(found) == 0
