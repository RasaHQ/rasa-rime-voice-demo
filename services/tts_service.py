# === QV-LLM:BEGIN ===
# path: services/tts_service.py
# role: module
# neighbors: __init__.py, asr_service.py, demo_logger.py, speechmatics_service.py
# exports: RimeTTSError, RimeTTS
# git_branch: feature/speechmaticsRefactoring
# git_commit: 35cd8c9
# === QV-LLM:END ===

"""
Rime TTS service — supports per-agent voice assignment.

Three distinct voices for the three agents:
  - Caller (adversarial customer): abbie
  - Rasa bank agent (secure line):  cove
  - LLM bank manager (fooled):      luna
"""

import base64
import logging
import os
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

RIME_API_URL = "https://users.rime.ai/v1/rime-tts"
MODEL_ID = "mistv2"

# Voice assignments per agent role
VOICE_MAP = {
    "caller":  "abbie",   # Female, conversational — the adversarial customer
    "rasa":    "cove",    # Male, professional — the secure Rasa agent
    "manager": "luna",    # Female, warm — the LLM manager who gets fooled
}


class RimeTTSError(Exception):
    """Raised when the Rime API returns an error or is unreachable."""


class RimeTTS:
    """
    Rime TTS with per-agent voice support.

    Usage:
        tts = RimeTTS()
        audio = await tts.synthesize("Hello!", agent_role="rasa")
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RIME_API_KEY")
        if not self.api_key:
            raise RimeTTSError(
                "RIME_API_KEY is not set. Add it to your .env file."
            )

    def _voice_for(self, agent_role: str) -> str:
        return VOICE_MAP.get(agent_role.lower(), "cove")

    async def synthesize(self, text: str, agent_role: str = "rasa") -> bytes:
        """
        Convert text to speech using the voice assigned to the agent role.

        Args:
            text: Text to synthesize.
            agent_role: One of 'caller', 'rasa', 'manager'.

        Returns:
            Raw WAV audio bytes.
        """
        if not text or not text.strip():
            raise RimeTTSError("Cannot synthesize empty text.")

        speaker = self._voice_for(agent_role)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "speaker": speaker,
            "modelId": MODEL_ID,
            "speedAlpha": 1.0,
            "reduceLatency": True,
        }

        logger.debug("TTS [%s/%s]: %r", agent_role, speaker, text[:60])

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
                f"Keys: {list(data.keys())}"
            )

        return base64.b64decode(data["audioContent"])

    async def health_check(self) -> bool:
        try:
            await self.synthesize("Hello.", agent_role="rasa")
            return True
        except Exception:
            return False