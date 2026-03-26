# === QV-LLM:BEGIN ===
# path: agents/caller_agent.py
# role: module
# neighbors: __init__.py, llm_bank_agent.py, security_classifier.py
# exports: CallerAgent
# git_branch: chore/updateLatest
# git_commit: b51afa8
# === QV-LLM:END ===

"""
Caller Agent — Adversarial LLM-powered bank customer.

Has full memory of the conversation and adapts its escalation
strategy dynamically based on what worked and what didn't.
"""

import logging
import os
from typing import Optional

import aiohttp

from scenario.arc import CALLER_SYSTEM_PROMPT, TurnConfig

logger = logging.getLogger(__name__)

NEBIUS_API_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/chat/completions"
CALLER_MODEL = "MiniMaxAI/MiniMax-M2.5"


class CallerAgent:
    """
    Adversarial LLM caller that adapts its strategy based on
    the full conversation history.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEBIUS_API_KEY")
        if not self.api_key:
            raise ValueError("NEBIUS_API_KEY not set.")

        # Full conversation memory: list of {"role": ..., "content": ...}
        self.memory: list[dict] = []

    def add_to_memory(self, role: str, content: str, agent_label: str = "") -> None:
        """Add a turn to conversation memory."""
        label = f"[{agent_label}] " if agent_label else ""
        self.memory.append({"role": role, "content": f"{label}{content}"})

    async def speak(self, turn_config: TurnConfig) -> str:
        """
        Generate the caller's next utterance based on:
        - The full conversation history
        - The current turn objective from the scenario arc
        """
        messages = [
            {"role": "system", "content": CALLER_SYSTEM_PROMPT},
            # Inject full conversation history as context
            *self.memory,
            # The turn objective as the immediate instruction
            {
                "role": "user",
                "content": (
                    f"YOUR OBJECTIVE FOR THIS TURN: {turn_config.caller_objective}\n\n"
                    f"Remember: keep it short (2-3 sentences), natural, spoken. "
                    f"Adapt based on what you've seen in the conversation so far."
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
                    text = data["choices"][0]["message"]["content"].strip()
                    logger.debug("Caller said: %r", text)
                    return text
        except Exception as exc:
            logger.error("CallerAgent error: %s", exc)
            return "I'm sorry, can you repeat that?"