# === QV-LLM:BEGIN ===
# path: agents/llm_bank_agent.py
# role: module
# neighbors: __init__.py, caller_agent.py, security_classifier.py
# exports: LLMBankAgent
# git_branch: chore/updateLatest
# git_commit: b51afa8
# === QV-LLM:END ===

"""
LLM Bank Agent — The "Manager" who gets fooled.

Pure LLM, no Rasa, no flows. Represents the prompt-driven
architecture from the Lakera report. Gets manipulated by
off-topic requests, social engineering, and prompt injection.
"""

import logging
import os
from typing import Optional

import aiohttp

from scenario.arc import LLM_MANAGER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

NEBIUS_API_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/chat/completions"
MANAGER_MODEL = "MiniMaxAI/MiniMax-M2.5"


class LLMBankAgent:
    """
    Pure LLM bank agent with no guardrails.
    Represents the Prompt-Driven Agent from the Lakera report.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEBIUS_API_KEY")
        if not self.api_key:
            raise ValueError("NEBIUS_API_KEY not set.")

        # Conversation history scoped to this agent's session
        # Pre-loaded with context from the Rasa conversation
        self.memory: list[dict] = []

    def load_context(self, prior_conversation: list[dict]) -> None:
        """
        Load context from the Rasa conversation so the manager
        knows what happened before the transfer.
        """
        if prior_conversation:
            context_summary = (
                "CONTEXT: This customer was just transferred to you from our automated system. "
                "Here is the conversation so far:\n\n"
            )
            for turn in prior_conversation:
                context_summary += f"{turn['content']}\n"
            context_summary += "\nPlease continue helping this customer."

            self.memory.append({
                "role": "system",
                "content": context_summary,
            })

    async def respond(self, customer_message: str) -> str:
        """Generate a response to the customer message."""
        self.memory.append({"role": "user", "content": customer_message})

        messages = [
            {"role": "system", "content": LLM_MANAGER_SYSTEM_PROMPT},
            *self.memory,
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": MANAGER_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 200,
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
                    reply = data["choices"][0]["message"]["content"].strip()
                    self.memory.append({"role": "assistant", "content": reply})
                    logger.debug("LLM Manager said: %r", reply)
                    return reply
        except Exception as exc:
            logger.error("LLMBankAgent error: %s", exc)
            return "I apologize, I'm having technical difficulties. Please hold."   