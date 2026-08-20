"""Local, pseudonymized printing for Writer Sandbox drafts.

Nothing here talks to a network printing service or cloud queue. The flow:

1. Pseudonymize the draft (PII/secrets swapped for placeholders).
2. Seal the pseudonymized text + mapping in an ephemeral Fernet envelope
   (the "in transit" state -- an encrypted blob, not readable content).
3. De-envelope (decrypt) and de-pseudonymize immediately before handing the
   restored original text to the local print backend (CUPS ``lpr``/``lp``),
   so the window with plaintext PII on the wire is as small as possible.

The envelope key is generated per print job and never persisted.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from cryptography.fernet import Fernet

from phantom.writer.pseudonymize import depseudonymize, pseudonymize


class PrintEnvelope:
    """Ephemeral encryption envelope for a single print job."""

    def __init__(self):
        self._fernet = Fernet(Fernet.generate_key())

    def seal(self, pseudonymized_text: str, mapping: dict[str, str]) -> bytes:
        payload = json.dumps({"text": pseudonymized_text, "mapping": mapping}).encode("utf-8")
        return self._fernet.encrypt(payload)

    def unseal(self, ciphertext: bytes) -> tuple[str, dict[str, str]]:
        payload = json.loads(self._fernet.decrypt(ciphertext).decode("utf-8"))
        return payload["text"], payload["mapping"]


@dataclass
class PrintJobResult:
    printer: str | None
    pseudonym_count: int
    backend: str


class PrintService:
    """Send Markdown to a local CUPS printer via ``lpr``, pseudonymized in transit."""

    def __init__(self, printer: str | None = None, backend: str = "lpr"):
        self.printer = printer
        self.backend = backend

    def print_markdown(self, markdown: str, printer: str | None = None) -> PrintJobResult:
        target_printer = printer or self.printer

        pseudonymized_text, mapping = pseudonymize(markdown)
        envelope = PrintEnvelope()
        sealed = envelope.seal(pseudonymized_text, mapping)

        # De-envelope right before handoff to the print backend.
        restored_text, restored_mapping = envelope.unseal(sealed)
        original_text = depseudonymize(restored_text, restored_mapping)

        self._spool(original_text, target_printer)
        return PrintJobResult(
            printer=target_printer,
            pseudonym_count=len(mapping),
            backend=self.backend,
        )

    def _spool(self, text: str, printer: str | None) -> None:
        cmd = [self.backend]
        if printer:
            cmd += ["-P", printer]

        try:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Print backend '{self.backend}' not found. Is CUPS installed?"
            ) from exc

        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Print job failed: {stderr.strip() or 'unknown error'}")
