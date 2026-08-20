"""
Phantom NATS consumer.

Subscribes to ``cognition.insight.generated.v1`` and ingests Cerebro insights
into the FAISS vector store so RAG searches reflect new knowledge.
"""

import asyncio
import json
import logging
import os
import ssl

logger = logging.getLogger("phantom.nats.consumer")

_subscription = None
_nc = None


async def start_consumer() -> None:
    """
    Connect to NATS and subscribe to cognition.insight.generated.v1.

    Runs as a long-lived background asyncio task.  Non-fatal if NATS is
    unavailable — the subscription simply won't exist.
    """
    global _subscription, _nc
    nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
    nkey_seed = os.environ.get("NATS_NKEY_SEED", "").strip()
    nkey_seed_file = os.environ.get("NATS_NKEY_SEED_FILE", "").strip()
    ca_file = os.environ.get("NATS_CA_FILE", "").strip()
    cert_file = os.environ.get("NATS_CLIENT_CERT_FILE", "").strip()
    key_file = os.environ.get("NATS_CLIENT_KEY_FILE", "").strip()
    try:
        import nats
        kwargs = {}
        if not nkey_seed and nkey_seed_file and os.path.exists(nkey_seed_file):
            with open(nkey_seed_file, encoding="utf-8") as handle:
                for line in handle:
                    candidate = line.strip()
                    if candidate and not candidate.startswith("#"):
                        nkey_seed = candidate
                        break
        if nkey_seed:
            kwargs["nkeys_seed_str"] = nkey_seed
        if nats_url.startswith("tls://") or ca_file or cert_file or key_file:
            tls_context = ssl.create_default_context(cafile=ca_file or None)
            if cert_file and key_file:
                tls_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
            kwargs["tls"] = tls_context
        _nc = await nats.connect(nats_url, **kwargs)
        _subscription = await _nc.subscribe(
            "cognition.insight.generated.v1",
            cb=_handle_insight,
        )
        logger.info(
            "NATS consumer subscribed to cognition.insight.generated.v1 @ %s", nats_url
        )
        # Keep the connection alive until stop_consumer() is called
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("NATS consumer failed (non-fatal): %s", exc)


async def stop_consumer() -> None:
    """Unsubscribe and drain the consumer connection."""
    global _subscription, _nc
    if _subscription is not None:
        try:
            await _subscription.unsubscribe()
        except Exception:
            pass
        _subscription = None
    if _nc is not None and not _nc.is_closed:
        try:
            await _nc.drain()
        except Exception:
            pass
        _nc = None


async def _handle_insight(msg) -> None:
    """Handle a cognition.insight.generated.v1 event from Cerebro."""
    try:
        payload = json.loads(msg.data.decode())
        logger.info(
            "Received cognition insight from Cerebro: correlation_id=%s artifacts=%s",
            payload.get("correlation_id", "?"),
            payload.get("artifacts_count", 0),
        )

        # Build a document to index: combine themes, concepts and summary
        themes = payload.get("themes", [])
        concepts = payload.get("concepts", [])
        summary = payload.get("summary", "")
        file_hash = payload.get("file_hash", "")

        document_text = " ".join(themes + concepts)
        if summary:
            document_text = f"{summary}\n{document_text}"

        if not document_text.strip():
            return

        # Import lazily to avoid heavy deps at module load time
        from phantom.api.app import get_embedding_generator, get_vector_store

        embedder = get_embedding_generator()
        store = get_vector_store()

        embeddings = embedder.encode([document_text])
        metadata = [
            {
                "source": "cerebro",
                "file_hash": file_hash,
                "correlation_id": payload.get("correlation_id", ""),
                "subject": "cognition.insight.generated.v1",
            }
        ]
        store.add(embeddings, [document_text], metadata)
        logger.info("Indexed Cerebro insight into FAISS vector store (hash=%s)", file_hash)

    except Exception as exc:
        logger.error("Error handling cognition insight: %s", exc)
