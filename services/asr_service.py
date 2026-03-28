# === QV-LLM:BEGIN ===
# path: services/asr_service.py
# role: module
# neighbors: __init__.py, demo_logger.py, speechmatics_service.py, tts_service.py
# exports: DeepgramASRError, DeepgramASR
# git_branch: feature/speechmaticsRefactoring
# git_commit: 6511069
# === QV-LLM:END ===

"""
Deepgram ASR (Automatic Speech Recognition) service.

Encapsulates all Deepgram API interaction. Used by both the demo
orchestrator and the test suite — no UI or demo logic lives here.
"""

import os
import logging
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"
DEFAULT_MODEL = "nova-2-general"


class DeepgramASRError(Exception):
    """Raised when the Deepgram API returns an error or is unreachable."""


class DeepgramASR:
    """
    Thin async wrapper around the Deepgram REST transcription API.

    Usage:
        asr = DeepgramASR()
        transcript = await asr.transcribe(Path("audio/input.wav"))
    """

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise DeepgramASRError(
                "DEEPGRAM_API_KEY is not set. "
                "Add it to your .env file or pass it explicitly."
            )
        self.model = model

    async def transcribe(self, audio_path: Path) -> str:
        """
        Transcribe a WAV audio file using Deepgram Nova-2.

        Args:
            audio_path: Path to a .wav audio file.

        Returns:
            The transcribed text string. Returns an empty string if
            no speech was detected.

        Raises:
            DeepgramASRError: On API error or connectivity failure.
            FileNotFoundError: If audio_path does not exist.
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }
        params = {
            "model": self.model,
            "smart_format": "true",
        }

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        logger.debug("Sending %d bytes to Deepgram (%s)", len(audio_data), audio_path.name)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEEPGRAM_API_URL,
                    headers=headers,
                    params=params,
                    data=audio_data,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        body = await response.text()
                        raise DeepgramASRError(
                            f"Deepgram returned HTTP {response.status}: {body}"
                        )
                    data = await response.json()
        except aiohttp.ClientError as exc:
            raise DeepgramASRError(f"Failed to reach Deepgram: {exc}") from exc

        try:
            transcript = (
                data["results"]["channels"][0]["alternatives"][0]["transcript"]
            )
        except (KeyError, IndexError) as exc:
            raise DeepgramASRError(
                f"Unexpected Deepgram response shape: {data}"
            ) from exc

        logger.debug("Transcript: %r", transcript)
        return transcript

    async def health_check(self) -> bool:
        """
        Verify the API key is valid by making a minimal request.

        Returns True if the key is accepted, False otherwise.
        Does not raise — safe to use in verify_setup.py.
        """
        try:
            headers = {"Authorization": f"Token {self.api_key}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.deepgram.com/v1/projects",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    return response.status == 200
        except Exception:
            return False