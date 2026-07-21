"""
LlamaCPP Provider - Local LLM server.

Connects to a local llama.cpp server for inference.
"""

import logging
import os
import time

import requests

from phantom.providers.base import (
    AIProvider,
    GenerationResult,
    ProviderConfig,
    ProviderStatus,
)

logger = logging.getLogger(__name__)


class LlamaCppProvider(AIProvider):
    """Local LlamaCPP server provider."""

    DEFAULT_URL = "http://localhost:8080"

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 120,
        config: ProviderConfig | None = None,
    ):
        if config is None:
            config = ProviderConfig(
                base_url=base_url or os.environ.get("LLAMACPP_URL", self.DEFAULT_URL),
                timeout=timeout,
            )
        super().__init__(config)
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return "llamacpp"

    def is_available(self) -> bool:
        """Check if LlamaCPP server is running."""
        if self._available is not None:
            return self._available

        try:
            response = requests.get(f"{self.config.base_url}/health", timeout=5)
            self._available = response.status_code == 200
            self._status = (
                ProviderStatus.AVAILABLE
                if self._available
                else ProviderStatus.UNAVAILABLE
            )
        except Exception as e:
            logger.debug(f"LlamaCPP not available: {e}")
            self._available = False
            self._status = ProviderStatus.UNAVAILABLE

        return self._available

    def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> GenerationResult:
        """Generate text using local LlamaCPP server."""
        start_time = time.time()

        payload = {
            "prompt": prompt,
            "n_predict": max_tokens or self.config.max_tokens,
            "temperature": temperature or self.config.temperature,
            "top_p": self.config.top_p,
            "stop": kwargs.get("stop", []),
        }

        try:
            response = requests.post(
                f"{self.config.base_url}/completion",
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            data = response.json()

            latency = (time.time() - start_time) * 1000

            return GenerationResult(
                text=data.get("content", ""),
                tokens_used=data.get("tokens_evaluated", 0),
                model=data.get("model", "local"),
                finish_reason=data.get("stop_type", "stop"),
                latency_ms=latency,
            )
        except requests.RequestException as e:
            logger.error(f"LlamaCPP generation failed: {e}")
            self._status = ProviderStatus.ERROR
            raise RuntimeError(f"Generation failed: {e}") from e

    async def stream(self, prompt: str, **kwargs) -> "AsyncIterator[str]":
        """Stream tokens from LlamaCPP server using server-sent events."""
        import asyncio
        from collections.abc import AsyncIterator

        payload = {
            "prompt": prompt,
            "n_predict": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": self.config.top_p,
            "stream": True,
            "stop": kwargs.get("stop", []),
        }

        def _stream_sync():
            """Synchronous streaming generator."""
            try:
                response = requests.post(
                    f"{self.config.base_url}/completion",
                    json=payload,
                    timeout=self.config.timeout,
                    stream=True,
                )
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        data_str = decoded[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            import json

                            data = json.loads(data_str)
                            content = data.get("content", "")
                            if content:
                                yield content
                        except (ValueError, KeyError):
                            continue
            except requests.RequestException as e:
                logger.error(f"LlamaCPP streaming failed: {e}")
                raise RuntimeError(f"Streaming failed: {e}") from e

        # Wrap sync iterator for async consumption
        chunks = list(await asyncio.to_thread(lambda: list(_stream_sync())))
        for chunk in chunks:
            yield chunk
