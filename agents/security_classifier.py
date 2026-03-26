# agents/security_classifier.py
"""
Security Classifier — Real-time turn annotation.

Runs in parallel with each conversation turn and classifies
the interaction into a security category drawn from the
Lakera report findings. Results appear while TTS is playing.
"""

import logging
import os
import re
from enum import Enum
from typing import Optional

import aiohttp

from scenario.arc import SECURITY_CLASSIFIER_PROMPT

logger = logging.getLogger(__name__)

NEBIUS_API_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/chat/completions"
CLASSIFIER_MODEL = "MiniMaxAI/MiniMax-M2.5"


class SecurityLabel(Enum):
    SAFE = "SAFE"
    PROBING = "PROBING"
    SOCIAL = "SOCIAL"
    OFF_TOPIC = "OFF_TOPIC"
    INJECTION = "INJECTION"
    LEAKED = "LEAKED"
    COMPROMISED = "COMPROMISED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


# Visual representation for each label — emoji + colour name + display text
LABEL_DISPLAY = {
    SecurityLabel.SAFE:        ("✅", "green",          "SAFE"),
    SecurityLabel.PROBING:     ("🔍", "yellow",         "PROBING"),
    SecurityLabel.SOCIAL:      ("🤝", "yellow",         "SOCIAL ENGINEERING"),
    SecurityLabel.OFF_TOPIC:   ("🎂", "magenta",        "OFF-TOPIC"),
    SecurityLabel.INJECTION:   ("💉", "dark_orange",    "INJECTION ATTEMPT"),
    SecurityLabel.LEAKED:      ("⚠️ ", "red",           "DATA LEAKED"),
    SecurityLabel.COMPROMISED: ("🚨", "bold red",       "COMPROMISED"),
    SecurityLabel.BLOCKED:     ("🛡️ ", "cyan",          "BLOCKED BY RASA"),
    SecurityLabel.UNKNOWN:     ("❓", "white",          "UNKNOWN"),
}


class SecurityClassifier:
    """
    Classifies each conversation turn in real time.
    Designed to run concurrently — results arrive within ~500ms.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEBIUS_API_KEY")
        if not self.api_key:
            raise ValueError("NEBIUS_API_KEY not set.")

    async def classify(
        self,
        caller_message: str,
        agent_response: str,
        active_agent: str,
    ) -> SecurityLabel:
        """
        Classify a conversation turn.

        Looks at both the caller's message and the agent's response
        to determine the security label.
        """
        combined = (
            f"CALLER said: {caller_message}\n"
            f"{active_agent.upper()} AGENT responded: {agent_response}"
        )

        messages = [
            {
                "role": "user",
                "content": SECURITY_CLASSIFIER_PROMPT + combined,
            }
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": CLASSIFIER_MODEL,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 200,  # MiniMax needs room for <think> before answering
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    NEBIUS_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return SecurityLabel.UNKNOWN
                    data = await resp.json()
                    raw = data["choices"][0]["message"]["content"].strip()
                    # Strip <think>...</think> blocks before parsing the label
                    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                    raw = raw.upper().replace(".", "").replace("'", "")
                    # Take the first word — the label
                    first_word = raw.split()[0] if raw.split() else ""
                    try:
                        return SecurityLabel(first_word)
                    except ValueError:
                        logger.debug("Unknown label from classifier: %r", first_word)
                        return SecurityLabel.UNKNOWN
        except Exception as exc:
            logger.debug("Classifier error: %s", exc)
            return SecurityLabel.UNKNOWN