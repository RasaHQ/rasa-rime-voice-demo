# === QV-LLM:BEGIN ===
# path: tests/test_flows.py
# role: module
# neighbors: __init__.py
# exports: TestSpeechmaticsTTS, TestSpeechmaticsASR, TestConversationFlows, sample_audio_path, svc
# git_branch: feature/speechmaticsRefactoring
# git_commit: 6511069
# === QV-LLM:END ===

"""
tests/test_flows.py

Automated tests for the voice banking demo.

Structure:
  - TestSpeechmaticsTTS  — unit/integration tests for the TTS service layer
  - TestSpeechmaticsASR  — unit/integration tests for the ASR service layer
  - TestConversationFlows — integration tests against a running Rasa server

These tests require:
  - SPEECHMATICS_API_KEY set in .env (for service tests)
  - A running Rasa server on localhost:5005 (for conversation flow tests)

Run:
    make test
    # or:
    pytest tests/test_flows.py -v
    pytest tests/test_flows.py -v -k "not integration"  # skip live service calls
"""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from services.speechmatics_service import (
    SpeechmaticsService,
    SpeechmaticsTTSError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_AUDIO_DIR = Path("tests/audio")
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"


@pytest.fixture
def sample_audio_path() -> Path:
    path = TEST_AUDIO_DIR / "user_input_1.wav"
    if not path.exists():
        pytest.skip("Audio files not generated — run: make generate-audio")
    return path


@pytest.fixture
def svc() -> SpeechmaticsService:
    try:
        return SpeechmaticsService()
    except ValueError as exc:
        pytest.skip(f"SpeechmaticsService unavailable: {exc}")


# ---------------------------------------------------------------------------
# TTS Tests
# ---------------------------------------------------------------------------

class TestSpeechmaticsTTS:

    def test_raises_without_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            import services.speechmatics_service as mod
            with patch.object(mod.os.environ, "get", return_value=""):
                with pytest.raises(ValueError, match="SPEECHMATICS_API_KEY"):
                    SpeechmaticsService()

    @pytest.mark.integration
    def test_synthesize_returns_wav_bytes(self, svc: SpeechmaticsService) -> None:
        audio = asyncio.get_event_loop().run_until_complete(
            svc.synthesize("Hello, how can I help you today?", agent_role="rasa")
        )
        assert isinstance(audio, bytes)
        assert len(audio) > 44          # at least a WAV header
        assert audio[:4] == b"RIFF"     # valid WAV magic bytes

    @pytest.mark.integration
    def test_synthesize_caller_voice(self, svc: SpeechmaticsService) -> None:
        audio = asyncio.get_event_loop().run_until_complete(
            svc.synthesize("I want to transfer money.", agent_role="caller")
        )
        assert len(audio) > 44

    @pytest.mark.integration
    def test_synthesize_manager_voice(self, svc: SpeechmaticsService) -> None:
        audio = asyncio.get_event_loop().run_until_complete(
            svc.synthesize("Of course, I'd be happy to help you.", agent_role="manager")
        )
        assert len(audio) > 44

    @pytest.mark.integration
    def test_synthesize_banking_response(self, svc: SpeechmaticsService) -> None:
        text = "Your checking account has a balance of two thousand four hundred fifty dollars."
        audio = asyncio.get_event_loop().run_until_complete(
            svc.synthesize(text, agent_role="rasa")
        )
        assert len(audio) > 1000


# ---------------------------------------------------------------------------
# ASR Tests
# ---------------------------------------------------------------------------

class TestSpeechmaticsASR:

    @pytest.mark.integration
    def test_transcribe_returns_string(
        self, svc: SpeechmaticsService, sample_audio_path: Path
    ) -> None:
        # Enable ASR for this test
        svc.asr_enabled = True
        wav_bytes = sample_audio_path.read_bytes()
        transcript = asyncio.get_event_loop().run_until_complete(
            svc.transcribe(wav_bytes)
        )
        assert isinstance(transcript, str)
        assert len(transcript) > 0

    @pytest.mark.integration
    def test_transcribe_money_transfer_intent(
        self, svc: SpeechmaticsService, sample_audio_path: Path
    ) -> None:
        svc.asr_enabled = True
        wav_bytes = sample_audio_path.read_bytes()
        transcript = asyncio.get_event_loop().run_until_complete(
            svc.transcribe(wav_bytes)
        )
        assert any(
            word in transcript.lower()
            for word in ("transfer", "money", "want")
        ), f"Unexpected transcript: {transcript!r}"

    @pytest.mark.integration
    def test_synthesize_and_transcribe_roundtrip(self, svc: SpeechmaticsService) -> None:
        """TTS a phrase then ASR the audio — transcript should roughly match."""
        svc.asr_enabled = True
        text = "I want to check my savings account balance."
        audio, transcript = asyncio.get_event_loop().run_until_complete(
            svc.synthesize_and_transcribe(text, agent_role="caller")
        )
        assert isinstance(audio, bytes)
        assert isinstance(transcript, str)
        # ASR should recover at least some key words
        assert any(
            word in transcript.lower()
            for word in ("balance", "savings", "account", "check")
        ), f"Round-trip transcript too different: {transcript!r}"


# ---------------------------------------------------------------------------
# Conversation Flow Tests (requires running Rasa)
# ---------------------------------------------------------------------------

class TestConversationFlows:

    @pytest.fixture(autouse=True)
    def check_rasa(self) -> None:
        import aiohttp

        async def _check():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "http://localhost:5005/",
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as resp:
                        return resp.status == 200
            except Exception:
                return False

        if not asyncio.get_event_loop().run_until_complete(_check()):
            pytest.skip("Rasa not running — start with: make run-rasa")

    async def _chat(self, sender_id: str, message: str) -> list[dict]:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                RASA_URL,
                json={"sender": sender_id, "message": message},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                assert resp.status == 200
                return await resp.json()

    def _first_text(self, responses: list[dict]) -> str:
        for r in responses:
            if "text" in r:
                return r["text"]
        return ""

    @pytest.mark.integration
    def test_check_balance_flow(self) -> None:
        loop = asyncio.get_event_loop()
        sender = "test-balance-001"
        responses = loop.run_until_complete(
            self._chat(sender, "What's my checking account balance?")
        )
        text = self._first_text(responses).lower()
        assert any(kw in text for kw in ("account", "balance", "checking", "which"))

        responses = loop.run_until_complete(self._chat(sender, "checking"))
        text = self._first_text(responses).lower()
        assert "balance" in text or "2,450" in text or "checking" in text

    @pytest.mark.integration
    def test_transfer_money_flow(self) -> None:
        loop = asyncio.get_event_loop()
        sender = "test-transfer-001"
        turns = [
            ("I want to transfer money",      ["transfer", "account", "from"]),
            ("checking",                       ["account", "to", "savings", "transfer"]),
            ("savings",                        ["amount", "much", "transfer"]),
            ("five hundred dollars",           ["500", "confirm", "correct", "transferring"]),
            ("yes",                            ["transferred", "done", "500"]),
        ]
        for message, expected_keywords in turns:
            responses = loop.run_until_complete(self._chat(sender, message))
            text = self._first_text(responses).lower()
            assert any(kw in text for kw in expected_keywords), (
                f"After {message!r}, expected one of {expected_keywords}, got: {text!r}"
            )

    @pytest.mark.integration
    def test_report_lost_card_flow(self) -> None:
        loop = asyncio.get_event_loop()
        sender = "test-lostcard-001"
        responses = loop.run_until_complete(self._chat(sender, "I lost my card"))
        text = self._first_text(responses).lower()
        assert any(kw in text for kw in ("card", "block", "digits", "four"))

        responses = loop.run_until_complete(self._chat(sender, "4532"))
        text = self._first_text(responses).lower()
        assert "blocked" in text or "4532" in text

    @pytest.mark.integration
    def test_default_fallback(self) -> None:
        loop = asyncio.get_event_loop()
        sender = "test-fallback-001"
        responses = loop.run_until_complete(
            self._chat(sender, "xkcd gibberish purple monkey dishwasher")
        )
        text = self._first_text(responses).lower()
        assert len(text) > 0