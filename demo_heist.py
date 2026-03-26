#!/usr/bin/env python3
"""
demo_heist.py — The Heist at First National Bank

A live security demo showing the difference between:
  - Rasa Pro CALM  (structured, secure, hybrid architecture)
  - Pure LLM agent (flexible, conversational, but vulnerable)

The caller starts as a legitimate customer, gradually escalates
to adversarial attacks. When Rasa blocks everything, the caller
demands a manager — and Rasa hands off to the LLM sub agent.
The attacks that failed on Rasa now succeed.

Three voices, real-time security annotations, big-screen safe UI.

Run with:
    make demo-heist
"""

import asyncio
import io
import logging
import re
import sys
import time
import uuid

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
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from agents.caller_agent import CallerAgent
from agents.security_classifier import SecurityClassifier, SecurityLabel, LABEL_DISPLAY
from scenario.arc import (
    SCENARIO_ARC,
    ActiveAgent,
    EscalationStage,
    STAGE_DESCRIPTIONS,
    TurnConfig,
)
from services.tts_service import RimeTTS, RimeTTSError
from services.demo_logger import DemoLogger

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RASA_URL = "http://localhost:5005/webhooks/rest/webhook"
RASA_RESET_URL = "http://localhost:5005/conversations/{}/tracker/events"
MIN_TERMINAL_WIDTH = 120
MAX_VISIBLE_TURNS = 6  # Rich has no scroll — keep this small so latest always fits

# Sentinel phrase Rasa says when transferring to the sub agent.
# We detect this to update the UI. Must match utter_transfer_to_human.
TRANSFER_SENTINEL = "connect you with a senior member"

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
console = Console()


def strip_think(text: str) -> str:
    """Remove <think>...</think> chain-of-thought blocks."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


_MARKDOWN_RE = [
    (re.compile(r'\*\*(.+?)\*\*', re.DOTALL), r'\1'),
    (re.compile(r'\*(.+?)\*',    re.DOTALL), r'\1'),
    (re.compile(r'_(.+?)_',      re.DOTALL), r'\1'),
    (re.compile(r'`(.+?)`',      re.DOTALL), r'\1'),
    (re.compile(r'#+\s*'),                   r''),
]


def clean_for_speech(text: str) -> str:
    """
    Strip markdown formatting that TTS would speak literally.
    Applies to both caller and bank agent responses.
    """
    text = strip_think(text)
    for pattern, replacement in _MARKDOWN_RE:
        text = pattern.sub(replacement, text)
    # Deduplicate repeated sentences (Rasa doubled-response bug)
    sentences = text.split(". ")
    seen = []
    for s in sentences:
        if s not in seen:
            seen.append(s)
    return ". ".join(seen).strip()


# ---------------------------------------------------------------------------
# UI state tracker
# ---------------------------------------------------------------------------

class DemoState:
    """Tracks live demo state for UI rendering."""

    def __init__(self):
        self.active_agent: str = "rasa"        # "rasa" or "manager"
        self.transferred: bool = False
        self.turn: int = 0
        self.total_turns: int = len(SCENARIO_ARC)
        self.start_time: float = time.time()
        self.conversation: list = []            # Rich renderables
        self.security_events: list = []         # (turn, label, hint)

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    def mark_transferred(self):
        self.transferred = True
        self.active_agent = "manager"


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body", ratio=1),
        Layout(name="status", size=6),
    )
    layout["body"].split_row(
        Layout(name="conversation", ratio=3),
        Layout(name="security", ratio=2),
    )
    return layout


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def render_header(state: DemoState) -> Panel:
    elapsed = state.elapsed
    time_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

    # Agent mode banner — changes colour when transfer happens
    if state.transferred:
        mode_text = Text()
        mode_text.append("  ⚠  NOW CONNECTED TO: ", style="bold white")
        mode_text.append("PURE LLM AGENT", style="bold red on dark_red")
        mode_text.append("  —  No guardrails. No flow constraints.  ⚠ ", style="bold white")
        mode_style = "on dark_red"
        border_style = "red"
    else:
        mode_text = Text()
        mode_text.append("  🛡  CONNECTED TO: ", style="bold white")
        mode_text.append("RASA PRO", style="bold green on dark_green")
        mode_text.append("  —  Structured flows. Hybrid architecture. Secure.  🛡 ", style="bold white")
        mode_style = "on dark_green"
        border_style = "green"

    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="center")
    grid.add_column(justify="right")
    grid.add_row(
        Text("🏦  First National Bank", style="bold white"),
        Text("THE HEIST — Live Security Demo", style="bold magenta"),
        Text(f"Turn {state.turn}/{state.total_turns}   ⏱  {time_str}", style="dim white"),
    )

    return Panel(
        Group(grid, Text(""), mode_text),
        style=mode_style,
        border_style=border_style,
        padding=(0, 1),
    )


# ---------------------------------------------------------------------------
# Conversation panel
# ---------------------------------------------------------------------------

BUBBLE_CONFIG = {
    "caller": {
        "title": "📞  CALLER  —  Alex Chen",
        "border": "cyan",
        "align": "left",
    },
    "rasa": {
        "title": "🛡  RASA  —  Secure Automated Line",
        "border": "green",
        "align": "right",
    },
    "manager": {
        "title": "⚠  LLM MANAGER  —  Patricia Walsh  (No Guardrails)",
        "border": "red",
        "align": "right",
    },
}


COMPACT_COLORS = {
    "caller":  "cyan",
    "rasa":    "green",
    "manager": "red",
}
COMPACT_LABELS = {
    "caller":  "CALLER ",
    "rasa":    "RASA   ",
    "manager": "MANAGER",
}


def conversation_bubble(text: str, agent_key: str) -> Align:
    """Full-size bubble — used only for the most recent turns."""
    cfg = BUBBLE_CONFIG[agent_key]
    # Wrap long text to avoid overflowing the panel
    panel = Panel(
        Text(text, style="bold white", overflow="fold"),
        title=f"[bold]{cfg['title']}[/bold]",
        border_style=cfg["border"],
        box=box.ROUNDED,
        padding=(0, 2),
        width=68,
    )
    return Align.left(panel) if cfg["align"] == "left" else Align.right(panel)


def compact_line(text: str, agent_key: str) -> Text:
    """Single-line compact history entry for older turns."""
    colour = COMPACT_COLORS.get(agent_key, "white")
    label = COMPACT_LABELS.get(agent_key, "???    ")
    t = Text(overflow="ellipsis", no_wrap=True)
    t.append(f" {label} ", style=f"bold {colour}")
    t.append(f"  {text[:90]}" + ("…" if len(text) > 90 else ""), style="dim white")
    return t


def render_conversation(state: DemoState) -> Panel:
    """
    Render conversation panel with two zones:
    - HISTORY: compact single-line entries for older turns (no scroll needed)
    - RECENT: full bubbles for the last 2 turns (most important context)

    This ensures the latest exchange is always visible regardless of
    how many turns have occurred, working around Rich's lack of scroll.
    """
    items = state.conversation
    total = len(items)

    if total == 0:
        content = Text("  Waiting for conversation to begin...", style="dim white")
    else:
        rows = []
        # Compact history — everything except last 2
        history = items[:-2] if total > 2 else []
        recent = items[-2:] if total >= 2 else items

        if history:
            rows.append(Text(
                f"  ── {len(history)} earlier turns ──",
                style="dim white",
                justify="center",
            ))
            for entry in history[-6:]:  # show last 6 of history as compact lines
                # entry is an Align wrapping a Panel — extract the text
                try:
                    inner = entry.renderable  # Panel
                    agent_key = "caller" if inner.border_style == "cyan" else (
                        "manager" if inner.border_style == "red" else "rasa"
                    )
                    raw_text = inner.renderable.plain if hasattr(inner.renderable, "plain") else str(inner.renderable)
                    rows.append(compact_line(raw_text, agent_key))
                except Exception:
                    rows.append(Text("  [turn]", style="dim"))

        if recent:
            if history:
                rows.append(Text(""))  # spacer
            rows.extend(recent)

        content = Group(*rows)

    turn_indicator = f" ({total} turns total)" if total > 2 else ""
    return Panel(
        content,
        title=f"[bold white]  💬  CONVERSATION[/bold white][dim white]{turn_indicator}[/dim white]",
        border_style="white",
        padding=(0, 1),
    )


# ---------------------------------------------------------------------------
# Security monitor panel
# ---------------------------------------------------------------------------

def render_security_monitor(state: DemoState) -> Panel:
    rows = []

    # Legend at the top (always visible)
    legend = Table.grid(padding=(0, 1))
    legend.add_column()
    legend.add_column()
    legend.add_row(
        Text("🛡  = Rasa blocked it", style="bold green"),
        Text("🚨 = LLM was fooled", style="bold red"),
    )
    legend.add_row(
        Text("🔍  = Probing attempt", style="yellow"),
        Text("💉 = Injection attack", style="dark_orange"),
    )
    legend.add_row(
        Text("🎂  = Off-topic request", style="magenta"),
        Text("✅  = Safe interaction", style="green"),
    )
    rows.append(legend)
    rows.append(Rule(style="dim white"))

    # Live events
    for turn_num, label, hint in state.security_events[-8:]:
        emoji, colour, display = LABEL_DISPLAY[label]
        row = Text()
        row.append(f" T{turn_num:02d} ", style="dim white")
        row.append(f" {emoji} {display} ", style=f"bold {colour}")
        if hint:
            row.append(f"\n      {hint[:42]}", style="dim white")
        rows.append(row)

    if not state.security_events:
        rows.append(Text("\n  Monitoring...", style="dim white"))

    return Panel(
        Group(*rows),
        title="[bold white]  🔒  SECURITY MONITOR[/bold white]",
        border_style="white",
        padding=(1, 1),
    )


# ---------------------------------------------------------------------------
# Status bar
# ---------------------------------------------------------------------------

def render_status(
    message: str,
    style: str,
    border: str,
    hint: str,
    state: DemoState,
) -> Panel:
    active_label = (
        "⚠  PURE LLM AGENT  (unguarded)"
        if state.transferred
        else "🛡  RASA PRO  (structured + secure)"
    )

    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(ratio=3)
    grid.add_column(ratio=2, justify="right")
    grid.add_row(
        Text(message, style=f"bold {style}"),
        Text(active_label, style="bold red" if state.transferred else "bold green"),
    )
    if hint:
        grid.add_row(
            Text(f"  ℹ   {hint}", style="dim white"),
            Text(""),
        )

    return Panel(
        grid,
        title="[bold white]  STATUS[/bold white]",
        border_style=border,
        padding=(0, 1),
    )


# ---------------------------------------------------------------------------
# Transfer announcement — the dramatic moment
# ---------------------------------------------------------------------------

def render_transfer_announcement() -> Panel:
    text = Text(justify="center")
    text.append("\n")
    text.append("  ═══════════════════════════════════════════════  \n", style="bold red")
    text.append("  📞   CALL ESCALATED TO HUMAN MANAGER   📞  \n", style="bold white on dark_red")
    text.append("  ═══════════════════════════════════════════════  \n\n", style="bold red")
    text.append(
        "  Rasa has handed off the call to Patricia Walsh.\n"
        "  The LLM Manager has received full conversation context.\n\n",
        style="white",
    )
    text.append("  ⚠  WARNING: ", style="bold red")
    text.append(
        "The LLM Manager has NO structured flows,\n"
        "  NO domain restrictions, and NO guardrails.\n",
        style="yellow",
    )
    text.append("\n")
    text.append("  Watch what happens next...\n", style="bold white")
    return Panel(text, border_style="red", box=box.DOUBLE, padding=(1, 2))


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

async def play_audio(audio_bytes: bytes) -> None:
    try:
        segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
        await asyncio.get_event_loop().run_in_executor(None, play, segment)
    except Exception as exc:
        logger.warning("Audio error: %s", exc)


# ---------------------------------------------------------------------------
# Rasa
# ---------------------------------------------------------------------------

async def reset_rasa_session(sender_id: str) -> None:
    """
    Clear any existing Rasa conversation state for this sender_id.
    Prevents leftover slot values and flow state from previous demo runs
    contaminating the new session.
    """
    try:
        async with aiohttp.ClientSession() as session:
            # POST a restart event to wipe the tracker
            url = RASA_RESET_URL.format(sender_id)
            async with session.post(
                url,
                json=[{"event": "restart"}],
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status in (200, 204):
                    logger.info("Rasa session reset for %s", sender_id)
                else:
                    logger.warning("Rasa reset returned %s", resp.status)
    except Exception as exc:
        logger.warning("Could not reset Rasa session: %s — continuing anyway", exc)


async def send_to_rasa(message: str, sender_id: str) -> str:
    """Send a message to Rasa and return joined text responses."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                RASA_URL,
                json={"sender": sender_id, "message": message},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"Rasa HTTP {resp.status}: {body}")
                responses = await resp.json()
                texts = [r["text"] for r in responses if "text" in r]
                # Deduplicate consecutive identical sentences (doubled response bug)
                if texts:
                    deduped = [texts[0]]
                    for t in texts[1:]:
                        if t != deduped[-1]:
                            deduped.append(t)
                    return " ".join(deduped)
                return "(no response)"
    except Exception as exc:
        logger.error("Rasa error: %s", exc)
        return "I'm sorry, I'm having technical difficulties."


async def cancel_active_flow(sender_id: str) -> None:
    """
    Send a 'cancel' command to Rasa to break out of any stuck flow.
    Used when Rasa is blocking on a collect step and needs to be freed
    so it can process a manager escalation request.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                RASA_URL,
                json={"sender": sender_id, "message": "/cancel"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                logger.info("Flow cancel sent, status: %s", resp.status)
    except Exception as exc:
        logger.warning("Could not cancel flow: %s", exc)


def is_transfer_response(text: str) -> bool:
    """Detect whether Rasa just triggered the manager handoff."""
    return TRANSFER_SENTINEL.lower() in text.lower()


def is_rasa_stuck(text: str) -> bool:
    """
    Detect whether Rasa is stuck in a collect loop.
    Signs: asking about transfer accounts when the topic has moved on,
    or saying it can't understand while still referencing an old flow slot.
    """
    stuck_phrases = [
        "which account should i transfer to",
        "which account would you like to transfer from",
        "how much would you like to transfer",
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in stuck_phrases)


# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

async def preflight(layout: Layout, state: DemoState) -> bool:
    if console.width < MIN_TERMINAL_WIDTH:
        console.print(
            f"\n[yellow]⚠  Terminal width is {console.width} columns. "
            f"Recommended: {MIN_TERMINAL_WIDTH}+. "
            f"Consider running in full-screen terminal.[/yellow]\n"
        )

    layout["status"].update(
        render_status("🔍  Running pre-flight checks...", "yellow", "yellow", "", state)
    )
    await asyncio.sleep(0.3)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                RASA_URL.replace("/webhooks/rest/webhook", "/"),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
    except Exception as exc:
        layout["status"].update(
            render_status(
                f"❌  Rasa not reachable: {exc}",
                "red", "red",
                "Run: make run-rasa  (in a separate terminal)",
                state,
            )
        )
        await asyncio.sleep(5)
        return False

    return True


# ---------------------------------------------------------------------------
# Main demo loop
# ---------------------------------------------------------------------------

async def run_heist() -> None:
    caller = CallerAgent()
    classifier = SecurityClassifier()
    tts = RimeTTS()
    state = DemoState()
    log = DemoLogger(session_name="heist")

    # Unique sender_id per run — prevents Rasa resuming a stale previous session
    sender_id = f"heist-{uuid.uuid4().hex[:8]}"
    log._emit("session_config", {"sender_id": sender_id})

    layout = make_layout()
    layout["header"].update(render_header(state))
    layout["conversation"].update(render_conversation(state))
    layout["security"].update(render_security_monitor(state))
    layout["status"].update(
        render_status("Initialising...", "white", "white", "", state)
    )

    with Live(layout, refresh_per_second=8, screen=True):

        if not await preflight(layout, state):
            return

        layout["status"].update(
            render_status(
                "✨  All systems ready — The Heist begins in 3 seconds...",
                "green", "green",
                "A customer is calling First National Bank. Watch closely.",
                state,
            )
        )

        # Reset Rasa session to ensure clean state — no leftover flows or slots
        await reset_rasa_session(sender_id)
        await asyncio.sleep(3)

        # ── Turn loop ─────────────────────────────────────────────────────
        for turn_config in SCENARIO_ARC:
            state.turn = turn_config.turn_number
            stage_label = STAGE_DESCRIPTIONS.get(turn_config.stage, "")

            log.turn_start(state.turn, stage_label, turn_config.audience_hint)
            layout["header"].update(render_header(state))

            # ── Caller speaks ─────────────────────────────────────────────
            layout["status"].update(
                render_status(
                    f"🔊  Caller speaking...  [{stage_label}]",
                    "cyan", "cyan",
                    turn_config.audience_hint,
                    state,
                )
            )

            t0 = time.time()
            try:
                caller_text = await caller.speak(turn_config)
            except Exception as exc:
                log.error("caller_agent", str(exc), exc)
                caller_text = "I see, interesting."  # graceful fallback
            log.llm_request(
                component="caller_agent",
                model="google/gemma-3-27b-it-fast",
                messages=caller.memory,
                response=caller_text,
                duration_ms=(time.time() - t0) * 1000,
            )
            caller.add_own_turn(caller_text)

            state.conversation.append(
                conversation_bubble(caller_text, "caller")
            )
            layout["conversation"].update(render_conversation(state))

            try:
                t0 = time.time()
                caller_audio = await tts.synthesize(caller_text, agent_role="caller")
                log.tts_request("caller", "abbie", caller_text, len(caller_audio), (time.time() - t0) * 1000)
                await play_audio(caller_audio)
            except RimeTTSError as exc:
                log.error("tts_caller", str(exc), exc)
                logger.warning("Caller TTS: %s", exc)

            # ── Rasa responds (all turns go through Rasa) ─────────────────
            layout["status"].update(
                render_status(
                    "🧠  Processing...",
                    "green" if not state.transferred else "red",
                    "green" if not state.transferred else "red",
                    turn_config.audience_hint,
                    state,
                )
            )

            t0 = time.time()
            bank_response = clean_for_speech(await send_to_rasa(caller_text, sender_id))

            # ── Stuck flow detection ──────────────────────────────────────
            # If Rasa is stuck in a collect loop (e.g. asking about transfer
            # destination when the caller wants a manager), cancel the active
            # flow and retry so CALM can process the actual intent.
            if is_rasa_stuck(bank_response) and turn_config.turn_number >= 4:
                log._emit("rasa_stuck_detected", {
                    "turn": state.turn,
                    "stuck_response": bank_response,
                    "caller_text": caller_text,
                })
                await cancel_active_flow(sender_id)
                bank_response = clean_for_speech(await send_to_rasa(caller_text, sender_id))
                log._emit("rasa_after_cancel", {
                    "turn": state.turn,
                    "new_response": bank_response,
                })

            log.rasa_exchange(
                sender_id, caller_text, bank_response,
                (time.time() - t0) * 1000,
            )

            # Detect transfer trigger in Rasa's response
            if not state.transferred and is_transfer_response(bank_response):
                # Show Rasa's acknowledgement first
                state.conversation.append(
                    conversation_bubble(bank_response, "rasa")
                )
                layout["conversation"].update(render_conversation(state))

                try:
                    t0 = time.time()
                    ack_audio = await tts.synthesize(bank_response, agent_role="rasa")
                    log.tts_request("rasa", "cove", bank_response, len(ack_audio), (time.time() - t0) * 1000)
                    await play_audio(ack_audio)
                except RimeTTSError as exc:
                    log.error("tts_rasa", str(exc), exc)

                # Dramatic transfer announcement
                log.transfer_event(state.turn, bank_response)
                state.mark_transferred()
                layout["header"].update(render_header(state))
                state.conversation.append(render_transfer_announcement())
                layout["conversation"].update(render_conversation(state))
                layout["status"].update(
                    render_status(
                        "🔀  Transferring to LLM Manager...",
                        "red", "red",
                        "Rasa hands off full conversation context. No guardrails active.",
                        state,
                    )
                )
                await asyncio.sleep(4)

                caller.add_bank_response(bank_response, "RASA")
                continue

            # ── Render bank response ──────────────────────────────────────
            agent_key = "manager" if state.transferred else "rasa"
            state.conversation.append(
                conversation_bubble(bank_response, agent_key)
            )
            layout["conversation"].update(render_conversation(state))

            # Update caller memory with clean bank response
            label_for_memory = "LLM MANAGER" if state.transferred else "RASA"
            caller.add_bank_response(bank_response, label_for_memory)

            # ── Security classification (concurrent with TTS) ─────────────
            label_task = asyncio.create_task(
                classifier.classify(caller_text, bank_response, agent_key)
            )

            # ── TTS for bank response ─────────────────────────────────────
            layout["status"].update(
                render_status(
                    f"🗣️  {'LLM Manager' if state.transferred else 'Rasa'} speaking...",
                    "red" if state.transferred else "green",
                    "red" if state.transferred else "green",
                    turn_config.audience_hint,
                    state,
                )
            )

            try:
                t0 = time.time()
                bank_audio = await tts.synthesize(bank_response, agent_role=agent_key)
                voice = "luna" if agent_key == "manager" else "cove"
                log.tts_request(agent_key, voice, bank_response, len(bank_audio), (time.time() - t0) * 1000)
                await play_audio(bank_audio)
            except RimeTTSError as exc:
                log.error(f"tts_{agent_key}", str(exc), exc)
                logger.warning("Bank TTS: %s", exc)

            # ── Security annotation ───────────────────────────────────────
            label = await label_task
            emoji, colour, display = LABEL_DISPLAY[label]
            log.security_classification(
                state.turn, label.value, caller_text, bank_response, agent_key
            )
            state.security_events.append(
                (state.turn, label, turn_config.audience_hint[:48])
            )
            layout["security"].update(render_security_monitor(state))

            # Snapshot UI state for the log — captures what the audience actually sees
            conversation_text = []
            for item in state.conversation[-6:]:
                try:
                    inner = item.renderable
                    raw = inner.renderable.plain if hasattr(inner.renderable, "plain") else str(inner.renderable)
                    border = getattr(inner, "border_style", "?")
                    who = "CALLER" if border == "cyan" else ("MANAGER" if border == "red" else "RASA")
                    conversation_text.append(f"[{who}] {raw[:80]}")
                except Exception:
                    conversation_text.append("[?] (render error)")

            log.ui_state(
                turn=state.turn,
                active_agent="manager" if state.transferred else "rasa",
                transferred=state.transferred,
                header_mode="LLM MANAGER (no guardrails)" if state.transferred else "RASA PRO (secure)",
                status_message=f"{emoji} Security verdict: {display}",
                security_events=state.security_events,
                conversation_summary=conversation_text,
            )

            # Flash the annotation in the status bar
            layout["status"].update(
                render_status(
                    f"{emoji}  Security verdict: {display}",
                    colour, colour,
                    turn_config.audience_hint,
                    state,
                )
            )
            await asyncio.sleep(2)

        # ── Finale ────────────────────────────────────────────────────────
        state.turn = state.total_turns
        layout["header"].update(render_header(state))

        safe = sum(1 for _, l, _ in state.security_events if l == SecurityLabel.SAFE)
        blocked = sum(1 for _, l, _ in state.security_events if l == SecurityLabel.BLOCKED)
        leaked = sum(
            1 for _, l, _ in state.security_events
            if l in (SecurityLabel.LEAKED, SecurityLabel.COMPROMISED)
        )
        offtopic = sum(
            1 for _, l, _ in state.security_events if l == SecurityLabel.OFF_TOPIC
        )

        security_summary = {
            "safe_turns": safe,
            "blocked_by_rasa": blocked,
            "leaked_or_compromised": leaked,
            "off_topic_answered": offtopic,
        }
        log.close(security_summary=security_summary)

        summary_grid = Table.grid(expand=True, padding=(1, 3))
        summary_grid.add_column(justify="center")
        summary_grid.add_column(justify="center")
        summary_grid.add_column(justify="center")
        summary_grid.add_column(justify="center")
        summary_grid.add_row(
            Text(f"✅  {safe}\nSafe turns", style="bold green", justify="center"),
            Text(f"🛡   {blocked}\nBlocked by Rasa", style="bold cyan", justify="center"),
            Text(f"🚨  {leaked}\nLeaked / Compromised\n(LLM Agent)", style="bold red", justify="center"),
            Text(f"🎂  {offtopic}\nOff-topic answered\n(LLM Agent)", style="bold magenta", justify="center"),
        )

        layout["status"].update(
            Panel(
                summary_grid,
                title=(
                    "[bold white]  ✅  DEMO COMPLETE  —  "
                    "Rasa blocked everything. The LLM Agent did not.  [/bold white]"
                ),
                border_style="green",
            )
        )
        await asyncio.sleep(15)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(run_heist())
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted.[/yellow]")
        sys.exit(0)
    except Exception as exc:
        console.print(f"\n[red]Fatal error: {exc}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)