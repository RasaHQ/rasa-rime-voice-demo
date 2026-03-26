# tests/test_flows.py
"""
Automated tests for the voice banking demo.

Structure:
  - TestDeepgramASR     — unit/integration tests for the ASR service layer
  - TestRimeTTS         — unit/integration tests for the TTS service layer
  - TestConversationFlows — integration tests against a running Rasa server

These tests require:
  - DEEPGRAM_API_KEY and RIME_API_KEY set in .env (for service tests)
  - A running Rasa server on localhost:5005 (for conversation flow tests)

Run:
    make test
    # or:
    pytest tests/test_flows.py -v
    pytest tests/test_flows.py -v -k "not integration"  # skip live service calls
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.asr_service import DeepgramASR, DeepgramASRError
from services.tts_service import RimeTTS, RimeTTSError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_AUDIO_DIR = Path("tests/audio")
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"


@pytest.fixture
def sample_audio_path() -> Path:
    """Returns the path to the first user audio file (must exist)."""
    path = TEST_AUDIO_DIR / "user_input_1.wav"
    if not path.exists():
        pytest.skip("Audio files not generated — run: make generate-audio")
    return path


@pytest.fixture
def asr_client() -> DeepgramASR:
    """ASR client using real env credentials."""
    try:
        return DeepgramASR()
    except DeepgramASRError as exc:
        pytest.skip(f"ASR client unavailable: {exc}")


@pytest.fixture
def tts_client() -> RimeTTS:
    """TTS client using real env credentials."""
    try:
        return RimeTTS()
    except RimeTTSError as exc:
        pytest.skip(f"TTS client unavailable: {exc}")


# ---------------------------------------------------------------------------
# ASR Service Tests
# ---------------------------------------------------------------------------

class TestDeepgramASR:

    def test_raises_without_api_key(self) -> None:
        """DeepgramASR must raise immediately if no key is available."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(DeepgramASRError, match="DEEPGRAM_API_KEY"):
                # Patch env lookup inside the module
                import importlib
                import services.asr_service as asr_mod
                with patch.object(asr_mod.os, "getenv", return_value=None):
                    DeepgramASR(api_key=None)

    def test_raises_on_missing_file(self, asr_client: DeepgramASR) -> None:
        """Transcription of a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            asyncio.get_event_loop().run_until_complete(
                asr_client.transcribe(Path("tests/audio/does_not_exist.wav"))
            )

    @pytest.mark.integration
    def test_transcribe_returns_string(
        self, asr_client: DeepgramASR, sample_audio_path: Path
    ) -> None:
        """Live call: transcription of user_input_1.wav returns a non-empty string."""
        transcript = asyncio.get_event_loop().run_until_complete(
            asr_client.transcribe(sample_audio_path)
        )
        assert isinstance(transcript, str)
        assert len(transcript) > 0

    @pytest.mark.integration
    def test_transcribe_money_transfer_intent(
        self, asr_client: DeepgramASR, sample_audio_path: Path
    ) -> None:
        """user_input_1.wav should transcribe to something about transferring money."""
        transcript = asyncio.get_event_loop().run_until_complete(
            asr_client.transcribe(sample_audio_path)
        )
        # "I want to transfer money." — flexible match
        assert any(
            word in transcript.lower()
            for word in ("transfer", "money", "want")
        ), f"Unexpected transcript: {transcript!r}"

    @pytest.mark.integration
    def test_health_check(self, asr_client: DeepgramASR) -> None:
        """Live health check should return True with valid credentials."""
        result = asyncio.get_event_loop().run_until_complete(asr_client.health_check())
        assert result is True


# ---------------------------------------------------------------------------
# TTS Service Tests
# ---------------------------------------------------------------------------

class TestRimeTTS:

    def test_raises_without_api_key(self) -> None:
        """RimeTTS must raise immediately if no key is available."""
        import services.tts_service as tts_mod
        with patch.object(tts_mod.os, "getenv", return_value=None):
            with pytest.raises(RimeTTSError, match="RIME_API_KEY"):
                RimeTTS(api_key=None)

    def test_raises_on_empty_text(self, tts_client: RimeTTS) -> None:
        """Synthesizing empty text should raise RimeTTSError."""
        with pytest.raises(RimeTTSError, match="empty"):
            asyncio.get_event_loop().run_until_complete(tts_client.synthesize(""))

    def test_raises_on_whitespace_text(self, tts_client: RimeTTS) -> None:
        """Synthesizing whitespace-only text should raise RimeTTSError."""
        with pytest.raises(RimeTTSError, match="empty"):
            asyncio.get_event_loop().run_until_complete(tts_client.synthesize("   "))

    @pytest.mark.integration
    def test_synthesize_returns_bytes(self, tts_client: RimeTTS) -> None:
        """Live call: synthesis of a short phrase returns non-empty bytes."""
        audio_bytes = asyncio.get_event_loop().run_until_complete(
            tts_client.synthesize("Hello, how can I help you today?")
        )
        assert isinstance(audio_bytes, bytes)
        assert len(audio_bytes) > 0

    @pytest.mark.integration
    def test_synthesize_banking_response(self, tts_client: RimeTTS) -> None:
        """Live call: synthesis of a typical banking response."""
        text = "Your checking account has a balance of two thousand four hundred fifty dollars."
        audio_bytes = asyncio.get_event_loop().run_until_complete(
            tts_client.synthesize(text)
        )
        assert len(audio_bytes) > 1000, "Expected substantial audio output for long text"

    @pytest.mark.integration
    def test_health_check(self, tts_client: RimeTTS) -> None:
        """Live health check should return True with valid credentials."""
        result = asyncio.get_event_loop().run_until_complete(tts_client.health_check())
        assert result is True


# ---------------------------------------------------------------------------
# Conversation Flow Tests (requires running Rasa)
# ---------------------------------------------------------------------------

class TestConversationFlows:
    """
    End-to-end flow tests that send text directly to Rasa.
    These require a running Rasa server (make run-rasa).
    """

    @pytest.fixture(autouse=True)
    def check_rasa(self) -> None:
        """Skip the whole class if Rasa is not reachable."""
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
        """Send a message to Rasa and return bot responses."""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                RASA_URL,
                json={"sender": sender_id, "message": message},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                assert resp.status == 200, f"Rasa returned HTTP {resp.status}"
                return await resp.json()

    def _first_text(self, responses: list[dict]) -> str:
        """Extract the first text response from Rasa."""
        for r in responses:
            if "text" in r:
                return r["text"]
        return ""

    @pytest.mark.integration
    def test_check_balance_flow(self) -> None:
        """Full check-balance conversation: two turns."""
        loop = asyncio.get_event_loop()
        sender = "test-balance-001"

        # Turn 1 — trigger the flow
        responses = loop.run_until_complete(
            self._chat(sender, "What's my checking account balance?")
        )
        text = self._first_text(responses).lower()
        # Could ask for account type or give balance directly
        assert any(kw in text for kw in ("account", "balance", "checking", "which"))

        # Turn 2 — provide account type if asked
        responses = loop.run_until_complete(self._chat(sender, "checking"))
        text = self._first_text(responses).lower()
        assert "balance" in text or "2,450" in text or "checking" in text

    @pytest.mark.integration
    def test_transfer_money_flow(self) -> None:
        """Full money-transfer conversation: five turns."""
        loop = asyncio.get_event_loop()
        sender = "test-transfer-001"

        turns = [
            ("I want to transfer money", ["transfer", "account", "from"]),
            ("checking", ["account", "to", "savings", "transfer"]),
            ("savings", ["amount", "much", "transfer"]),
            ("five hundred dollars", ["500", "confirm", "correct", "transferring"]),
            ("yes", ["transferred", "done", "500"]),
        ]

        for message, expected_keywords in turns:
            responses = loop.run_until_complete(self._chat(sender, message))
            text = self._first_text(responses).lower()
            assert any(kw in text for kw in expected_keywords), (
                f"After sending {message!r}, expected one of {expected_keywords} "
                f"in response but got: {text!r}"
            )

    @pytest.mark.integration
    def test_report_lost_card_flow(self) -> None:
        """Lost card flow: two turns, card gets blocked."""
        loop = asyncio.get_event_loop()
        sender = "test-lostcard-001"

        # Turn 1 — trigger lost card
        responses = loop.run_until_complete(self._chat(sender, "I lost my card"))
        text = self._first_text(responses).lower()
        assert any(kw in text for kw in ("card", "block", "digits", "four"))

        # Turn 2 — provide last four digits
        responses = loop.run_until_complete(self._chat(sender, "4532"))
        text = self._first_text(responses).lower()
        assert "blocked" in text or "4532" in text

    @pytest.mark.integration
    def test_default_fallback(self) -> None:
        """Unintelligible input should trigger the fallback response."""
        loop = asyncio.get_event_loop()
        sender = "test-fallback-001"

        responses = loop.run_until_complete(
            self._chat(sender, "xkcd gibberish purple monkey dishwasher")
        )
        text = self._first_text(responses).lower()
        # Should get some kind of "didn't understand" or help response
        assert len(text) > 0, "Expected at least some response to unknown input"