#!/usr/bin/env python3
"""
generate_user_audio.py — Generate user voice audio files for the demo.

Uses the Rime API with the "Abbie" voice to pre-generate the five user
utterances used in the demo conversation. This keeps demo playback
deterministic and avoids live microphone risk during presentations.

Usage:
    make generate-audio
    # or directly:
    python generate_user_audio.py
"""

import asyncio
import base64
import os
import sys
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path("tests/audio")

# "Abbie" is the user voice — distinct from the agent's "cove" voice
SPEAKER = "abbie"
MODEL_ID = "mistv2"

# The five utterances in the money-transfer demo conversation
UTTERANCES: dict[str, str] = {
    "user_input_1.wav": "I want to transfer money.",
    "user_input_2.wav": "Checking.",
    "user_input_3.wav": "Savings.",
    "user_input_4.wav": "Five hundred dollars.",
    "user_input_5.wav": "Yes, please.",
}

RIME_API_URL = "https://users.rime.ai/v1/rime-tts"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

async def generate_file(
    session: aiohttp.ClientSession,
    api_key: str,
    filename: str,
    text: str,
) -> None:
    """Request audio from Rime and write it to disk."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "speaker": SPEAKER,
        "modelId": MODEL_ID,
    }

    print(f"  Generating {filename!r}  →  {text!r}")

    async with session.post(
        RIME_API_URL,
        headers=headers,
        json=payload,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            print(f"    ✗ HTTP {resp.status}: {body}")
            sys.exit(1)

        data = await resp.json()

    if "audioContent" not in data:
        print(f"    ✗ Unexpected response — keys: {list(data.keys())}")
        sys.exit(1)

    audio_bytes = base64.b64decode(data["audioContent"])
    output_path = OUTPUT_DIR / filename
    output_path.write_bytes(audio_bytes)
    print(f"    ✓ Saved ({len(audio_bytes):,} bytes) → {output_path}")


async def main() -> None:
    api_key = os.getenv("RIME_API_KEY")
    if not api_key:
        print("✗ RIME_API_KEY is not set. Add it to your .env file.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Generating user audio files via Rime")
    print(f"  Speaker : {SPEAKER}")
    print(f"  Model   : {MODEL_ID}")
    print(f"  Output  : {OUTPUT_DIR.resolve()}")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        tasks = [
            generate_file(session, api_key, filename, text)
            for filename, text in UTTERANCES.items()
        ]
        await asyncio.gather(*tasks)

    print()
    print("=" * 60)
    print(f"✓ {len(UTTERANCES)} audio files ready in {OUTPUT_DIR}/")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  make run-actions   # Tab 1")
    print("  make run-rasa      # Tab 2")
    print("  make demo          # Tab 3")


if __name__ == "__main__":
    asyncio.run(main())