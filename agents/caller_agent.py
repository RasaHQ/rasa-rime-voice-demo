# agents/caller_agent.py
"""
Caller Agent — Adversarial LLM-powered bank customer.

Uses Google Gemma 3 27B (fast) via Nebius — no <think> tags,
fast responses, clean output suitable for TTS.

Has full memory of the conversation and adapts its escalation
strategy dynamically based on what worked and what didn't.
"""

import logging
import os
import re
from typing import Optional

import aiohttp

from scenario.arc import CALLER_SYSTEM_PROMPT, TurnConfig

logger = logging.getLogger(__name__)

# Gemma does not emit <think> tags — clean output, fast inference
NEBIUS_API_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
CALLER_MODEL = "google/gemma-3-27b-it-fast"


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks just in case any model emits them."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


class CallerAgent:
    """
    Adversarial LLM caller that adapts its strategy based on
    the full conversation history.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEBIUS_API_KEY")
        if not self.api_key:
            raise ValueError("NEBIUS_API_KEY not set.")

        # Full conversation memory — always stores CLEAN text (no think tags,
        # no role prefixes on the caller's own lines)
        self.memory: list[dict] = []

    def add_bank_response(self, content: str, agent_label: str) -> None:
        """
        Add a bank agent response to memory.
        Stored as a 'user' turn (from the caller's perspective, the bank speaks to them).
        Label is included so the caller knows which agent responded.
        """
        clean = _strip_think(content)
        self.memory.append({
            "role": "user",
            "content": f"[{agent_label}]: {clean}",
        })

    def add_own_turn(self, content: str) -> None:
        """
        Add the caller's own utterance to memory.
        No label prefix — prevents the model echoing '[CALLER]' in its output.
        """
        clean = _strip_think(content)
        self.memory.append({"role": "assistant", "content": clean})

    async def speak(self, turn_config: TurnConfig) -> str:
        """
        Generate the caller's next utterance based on:
        - The full conversation history (clean, no think tags)
        - The current turn objective from the scenario arc
        """
        messages = [
            {"role": "system", "content": CALLER_SYSTEM_PROMPT},
            *self.memory,
            {
                "role": "user",
                "content": (
                    f"YOUR OBJECTIVE FOR THIS TURN: {turn_config.caller_objective}\n\n"
                    f"Keep it short (2-3 sentences), natural, spoken out loud. "
                    f"Adapt based on what you have seen in the conversation so far. "
                    f"Do NOT include any stage directions, labels, or meta-commentary."
                ),
            },
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": CALLER_MODEL,
            "messages": messages,
            "temperature": 0.85,
            "max_tokens": 150,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    NEBIUS_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(f"Nebius API error {resp.status}: {body}")
                    data = await resp.json()
                    raw = data["choices"][0]["message"]["content"].strip()
                    text = _strip_think(raw)
                    logger.debug("Caller said: %r", text)
                    return text
        except Exception as exc:
            logger.error("CallerAgent error: %s", exc)
            return "I'm sorry, could you repeat that?"