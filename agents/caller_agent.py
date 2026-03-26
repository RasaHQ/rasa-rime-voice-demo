# === QV-LLM:BEGIN ===
# path: agents/caller_agent.py
# role: module
# neighbors: __init__.py, security_classifier.py
# exports: CallerAgent
# git_branch: chore/updateLatest
# git_commit: e110917
# === QV-LLM:END ===

"""
Caller Agent — Adversarial LLM-powered bank customer.

Uses Google Gemma 3 27B (fast) via Nebius.

Gemma strictly requires:
  1. First non-system message must be 'user'
  2. Roles must alternate user/assistant/user/assistant/...

Memory perspective (counterintuitive but correct):
  - Caller's own turns → role: 'user'
  - Bank responses    → role: 'assistant'

Gemma's system prompt tells it to BE Alex Chen, so it always generates
the next 'assistant' reply. The role labels are just structural constraints
for the API — the system prompt carries the persona.

This gives us the correct sequence every turn:
  Turn 1:  [system] [user(objective)]
  Turn 2:  [system] [user(caller)] [assistant(bank)] [user(objective)]
  Turn 3:  [system] [user(caller)] [assistant(bank)] [user(caller)] [assistant(bank)] [user(objective)]
  ...always starts with user, always alternates.
"""

import logging
import os
import re
from typing import Optional

import aiohttp

from scenario.arc import CALLER_SYSTEM_PROMPT, TurnConfig

logger = logging.getLogger(__name__)

NEBIUS_API_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
CALLER_MODEL = "google/gemma-3-27b-it-fast"


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


class CallerAgent:

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEBIUS_API_KEY")
        if not self.api_key:
            raise ValueError("NEBIUS_API_KEY not set.")
        # Stored turns — caller=user, bank=assistant (see module docstring)
        self._turns: list[dict] = []

    def add_bank_response(self, content: str, agent_label: str) -> None:
        """Bank response → stored as 'assistant'. Merge if last was also assistant."""
        clean = _strip_think(content)
        text = f"[{agent_label}]: {clean}"
        if self._turns and self._turns[-1]["role"] == "assistant":
            self._turns[-1]["content"] += f"\n{text}"
        else:
            self._turns.append({"role": "assistant", "content": text})

    def add_own_turn(self, content: str) -> None:
        """Caller speech → stored as 'user'. Merge if last was also user."""
        clean = _strip_think(content)
        if self._turns and self._turns[-1]["role"] == "user":
            self._turns[-1]["content"] += f" {clean}"
        else:
            self._turns.append({"role": "user", "content": clean})

    @property
    def memory(self) -> list[dict]:
        return self._turns

    async def speak(self, turn_config: TurnConfig) -> str:
        """
        Build a strictly alternating message list and call Gemma.

        The turn objective is delivered as a 'user' turn:
          - Turn 1 (empty memory): [system, user(objective)]
          - After bank spoke (last=assistant): append [user(objective)]
          - After we spoke (last=user): merge objective into that user turn
        """
        objective = (
            f"YOUR OBJECTIVE FOR THIS TURN: {turn_config.caller_objective}\n\n"
            f"Keep it short (2-3 sentences), natural, spoken out loud. "
            f"Do NOT include stage directions, labels, or meta-commentary. "
            f"Respond only with what Alex Chen would say on the phone."
        )

        history = [dict(t) for t in self._turns]

        if not history:
            history = [{"role": "user", "content": objective}]
        elif history[-1]["role"] == "assistant":
            # Bank just responded — add new user turn with objective
            history.append({"role": "user", "content": objective})
        else:
            # We just spoke — append objective to existing user turn
            history[-1]["content"] += f"\n\n{objective}"

        messages = [{"role": "system", "content": CALLER_SYSTEM_PROMPT}, *history]

        # Safety: log any alternation violations before sending
        non_sys = [m for m in messages if m["role"] != "system"]
        for i in range(1, len(non_sys)):
            if non_sys[i]["role"] == non_sys[i - 1]["role"]:
                logger.error(
                    "Role alternation violation at position %d: %s → %s",
                    i, non_sys[i - 1]["role"], non_sys[i]["role"],
                )

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