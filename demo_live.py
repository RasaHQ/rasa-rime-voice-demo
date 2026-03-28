#!/usr/bin/env python3
# === QV-LLM:BEGIN ===
# path: demo_live.py
# role: module
# neighbors: demo_heist.py, generate_user_audio.py, verify_setup.py
# exports: make_layout, set_status, update_chat, user_bubble, agent_bubble
# git_branch: feature/speechmaticsRefactoring
# git_commit: 35cd8c9
# === QV-LLM:END ===

"""
demo_live.py — Voice Orchestration Demo (Speechmatics edition)

Orchestrates a live banking conversation using:
  - Pre-generated user audio (Speechmatics Megan voice)
  - Speechmatics RT ASR for speech-to-text
  - Rasa Pro (CALM) for dialogue management
  - Speechmatics TTS for agent responses

Run this after starting the action server and Rasa:
  make run-actions   # Tab 1
  make run-rasa      # Tab 2
  make demo          # Tab 3 (this script)
"""

import asyncio
import io
import sys
import time
from pathlib import Path

import aiohttp
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.playback import play
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from services.speechmatics_service import SpeechmaticsService, SpeechmaticsTTSError

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"
AUDIO_DIR = Path("tests/audio")
SENDER_ID = "demo-user"
MAX_VISIBLE_BUBBLES = 6

CONVERSATION_STEPS = [
    {"file": "user_input_1.wav", "label": "Transfer Request"},
    {"file": "user_input_2.wav", "label": "Account Selection"},
    {"file": "user_input_3.wav", "label": "Account Destination"},
    {"file": "user_input_4.wav", "label": "Amount"},
    {"file": "user_input_5.wav", "label": "Confirmation"},
]

console = Console()


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="status", size=3),
    )
    return layout


def set_status(layout: Layout, message: str, style: str, border: str) -> None:
    layout["status"].update(
        Panel(Text(message, style=style), title="Status", border_style=border)
    )


def update_chat(layout: Layout, history: list) -> None:
    visible = history[-MAX_VISIBLE_BUBBLES:]
    layout["main"].update(
        Panel(
            Group(*visible),
            title="Conversation Log",
            border_style="white",
            padding=(1, 1),
        )
    )


def user_bubble(text: str) -> Align:
    return Align.left(
        Panel(
            Text(text, style="bright_white"),
            title="User",
            style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
            width=60,
        )
    )


def agent_bubble(text: str) -> Align:
    return Align.right(
        Panel(
            Text(text, style="bright_white"),
            title="Agent",
            style="green",
            box=box.ROUNDED,
            padding=(1, 2),
            width=60,
        )
    )


# ---------------------------------------------------------------------------
# Audio playback
# ---------------------------------------------------------------------------

async def play_audio_bytes(audio_bytes: bytes) -> None:
    try:
        segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
        await asyncio.get_event_loop().run_in_executor(None, play, segment)
    except Exception as exc:
        console.print(f"[red]Audio playback error: {exc}[/red]")


# ---------------------------------------------------------------------------
# Rasa interaction
# ---------------------------------------------------------------------------

async def send_to_rasa(message: str) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            RASA_URL,
            json={"sender": SENDER_ID, "message": message},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Rasa returned HTTP {resp.status}: {body}")
            return await resp.json()


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

async def preflight_check(layout: Layout) -> bool:
    set_status(layout, "🔍 Running pre-flight checks...", "bold yellow", "yellow")
    await asyncio.sleep(0.3)

    missing = [
        step["file"]
        for step in CONVERSATION_STEPS
        if not (AUDIO_DIR / step["file"]).exists()
    ]
    if missing:
        set_status(
            layout,
            f"❌ Missing audio files: {', '.join(missing)}\nRun: make generate-audio",
            "bold red", "red",
        )
        await asyncio.sleep(5)
        return False

    try:
        rasa_base = RASA_URL.replace("/webhooks/rest/webhook", "")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{rasa_base}/", timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
    except Exception as exc:
        set_status(layout, f"❌ Rasa not reachable: {exc}\nRun: make run-rasa", "bold red", "red")
        await asyncio.sleep(5)
        return False

    return True


# ---------------------------------------------------------------------------
# Main demo loop
# ---------------------------------------------------------------------------

async def run_demo() -> None:
    tts = SpeechmaticsService()

    layout = make_layout()
    header_text = Text(
        "🏦 Voice Orchestration — Rasa + Speechmatics",
        style="bold white on magenta",
        justify="center",
    )
    layout["header"].update(Panel(header_text, style="magenta"))
    history: list = []

    with Live(layout, refresh_per_second=10, screen=True):
        if not await preflight_check(layout):
            return

        set_status(layout, "✨ All systems ready — starting conversation...", "bold green", "green")
        await asyncio.sleep(1)

        for step in CONVERSATION_STEPS:
            audio_path = AUDIO_DIR / step["file"]

            # ── User speaks ──────────────────────────────────────────────
            set_status(layout, f"🔊 User speaking... [{step['label']}]", "bold cyan", "cyan")
            play(AudioSegment.from_wav(str(audio_path)))

            # ── ASR: transcribe the played audio ─────────────────────────
            set_status(layout, "⚡ Speechmatics transcribing...", "bold yellow", "yellow")
            try:
                audio_bytes = audio_path.read_bytes()
                transcript = await tts.transcribe(audio_bytes)
                if not transcript:
                    console.print("[yellow]Empty ASR transcript — skipping turn[/yellow]")
                    continue
            except Exception as exc:
                console.print(f"[red]ASR error: {exc}[/red]")
                continue

            history.append(user_bubble(transcript))
            update_chat(layout, history)

            # ── Rasa ─────────────────────────────────────────────────────
            set_status(layout, "🧠 Rasa thinking...", "bold green", "green")
            try:
                bot_responses = await send_to_rasa(transcript)
            except Exception as exc:
                console.print(f"[red]Rasa error: {exc}[/red]")
                continue

            # ── TTS & playback ───────────────────────────────────────────
            for response in bot_responses:
                agent_text = response.get("text", "")
                if not agent_text:
                    continue

                history.append(agent_bubble(agent_text))
                update_chat(layout, history)

                set_status(layout, "🗣️ Speechmatics speaking...", "bold magenta", "magenta")
                try:
                    audio_bytes = await tts.synthesize(agent_text, agent_role="rasa")
                    await play_audio_bytes(audio_bytes)
                except SpeechmaticsTTSError as exc:
                    console.print(f"[red]TTS error: {exc}[/red]")

            time.sleep(0.5)

        set_status(layout, "✨ Demo complete!", "bold white on green", "green")
        await asyncio.sleep(10)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        sys.exit(0)