# services/tts_service.py
"""
Rime TTS (Text-to-Speech) service.

Encapsulates all Rime API interaction. Used by both the demo
orchestrator and the test suite — no UI or demo logic lives here.
"""

import base64
import logging
import os

import aiohttp

logger = logging.getLogger(__name__)

RIME_API_URL = "https://users.rime.ai/v1/rime-tts"
DEFAULT_SPEAKER = "cove"
DEFAULT_MODEL = "mistv2"


class RimeTTSError(Exception):
    """Raised when the Rime API returns an error or is unreachable."""


class RimeTTS:
    """
    Thin async wrapper around the Rime TTS REST API.

    Usage:
        tts = RimeTTS()
        audio_bytes = await tts.synthesize("Hello, how can I help you?")
    """

    def __init__(
        self,
        api_key: str | None = None,
        speaker: str = DEFAULT_SPEAKER,
        model_id: str = DEFAULT_MODEL,
        speed_alpha: float = 1.0,
        reduce_latency: bool = True,
    ):
        self.api_key = api_key or os.getenv("RIME_API_KEY")
        if not self.api_key:
            raise RimeTTSError(
                "RIME_API_KEY is not set. "
                "Add it to your .env file or pass it explicitly."
            )
        self.speaker = speaker
        self.model_id = model_id
        self.speed_alpha = speed_alpha
        self.reduce_latency = reduce_latency

    async def synthesize(self, text: str) -> bytes:
        """
        Convert text to speech using Rime Mist v2.

        Args:
            text: The text to synthesize. Must be non-empty.

        Returns:
            Raw WAV audio bytes decoded from the Rime response.

        Raises:
            RimeTTSError: On API error, connectivity failure, or empty text.
        """
        if not text or not text.strip():
            raise RimeTTSError("Cannot synthesize empty text.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "speaker": self.speaker,
            "modelId": self.model_id,
            "speedAlpha": self.speed_alpha,
            "reduceLatency": self.reduce_latency,
        }

        logger.debug("Sending TTS request for: %r", text[:60])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    RIME_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise RimeTTSError(
                            f"Rime returned HTTP {response.status}: {body}"
                        )
                    data = await response.json()
        except aiohttp.ClientError as exc:
            raise RimeTTSError(f"Failed to reach Rime: {exc}") from exc

        if "audioContent" not in data:
            raise RimeTTSError(
                f"Unexpected Rime response — 'audioContent' missing. "
                f"Keys received: {list(data.keys())}"
            )

        audio_bytes = base64.b64decode(data["audioContent"])
        logger.debug("Received %d bytes of audio", len(audio_bytes))
        return audio_bytes

    async def health_check(self) -> bool:
        """
        Verify the Rime API key is valid with a minimal synthesis request.

        Returns True if the key is accepted, False otherwise.
        Does not raise — safe to use in verify_setup.py.
        """
        try:
            await self.synthesize("Hello.")
            return True
        except RimeTTSError:
            return False
        except Exception:
            return False