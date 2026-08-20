"""
Phantom NATS publisher.

Async NATS client wrapper with a synchronous bridge for use from
ThreadPoolExecutor workers (phantom_dag.py).

Usage (async context, e.g. FastAPI lifespan):
    await connect()
    await publish_async("ingest.file.sanitized.v1", {...})
    await drain()

Usage (sync/threaded context, e.g. PhantomPipeline.process_file):
    publish_sync("ingest.file.sanitized.v1", {...})
"""

import asyncio
import json
import logging
import os
import ssl

logger = logging.getLogger("phantom.nats.publisher")

# Module-level singletons, set during lifespan connect()
_nc = None   # nats.aio.client.Client
_loop = None  # asyncio event loop reference for thread-safe calls


async def connect() -> bool:
    """Connect to NATS. Call from async context (FastAPI lifespan). Non-fatal on failure."""
    global _nc, _loop
    nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
    nkey_seed = os.environ.get("NATS_NKEY_SEED", "").strip()
    nkey_seed_file = os.environ.get("NATS_NKEY_SEED_FILE", "").strip()
    ca_file = os.environ.get("NATS_CA_FILE", "").strip()
    cert_file = os.environ.get("NATS_CLIENT_CERT_FILE", "").strip()
    key_file = os.environ.get("NATS_CLIENT_KEY_FILE", "").strip()
    try:
        import nats
        _loop = asyncio.get_running_loop()
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
        logger.info("NATS publisher connected: %s (nkey=%s)", nats_url, bool(nkey_seed))
        return True
    except Exception as exc:
        logger.warning("NATS publisher connection failed (non-fatal): %s", exc)
        return False


async def drain() -> None:
    """Drain and close NATS connection. Call from async context (FastAPI lifespan)."""
    global _nc
    if _nc is not None and not _nc.is_closed:
        try:
            await _nc.drain()
            logger.info("NATS publisher drained")
        except Exception as exc:
            logger.warning("NATS publisher drain failed: %s", exc)
    _nc = None


def publish_sync(subject: str, payload: dict) -> None:
    """
    Publish from a synchronous/threaded context.

    Safe to call from ThreadPoolExecutor workers.  If NATS is not connected
    the call is silently skipped (non-blocking, non-fatal).
    """
    if _nc is None or _loop is None:
        return
    try:
        data = json.dumps(payload).encode()
        future = asyncio.run_coroutine_threadsafe(_nc.publish(subject, data), _loop)
        future.result(timeout=1.0)
    except Exception as exc:
        logger.warning("NATS publish_sync failed (non-fatal): %s", exc)


async def publish_async(subject: str, payload: dict) -> None:
    """Publish from an async context. No-op if not connected."""
    if _nc is None:
        return
    try:
        data = json.dumps(payload).encode()
        await _nc.publish(subject, data)
    except Exception as exc:
        logger.warning("NATS publish_async failed (non-fatal): %s", exc)
