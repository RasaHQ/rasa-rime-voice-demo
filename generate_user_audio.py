#!/usr/bin/env python3
# === QV-LLM:BEGIN ===
# path: generate_user_audio.py
# role: module
# neighbors: demo_heist.py, demo_live.py, verify_setup.py
# git_branch: feature/speechmaticsRefactoring
# git_commit: 35cd8c9
# === QV-LLM:END ===

"""
generate_user_audio.py — Generate user voice audio files for the demo.

Uses Speechmatics TTS with the "megan" voice (US female — Alex Chen)
to pre-generate the five user utterances used in demo_live.py.
This keeps demo playback deterministic and avoids live microphone
risk during presentations.

Usage:
    make generate-audio
    # or directly:
    python generate_user_audio.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path("tests/audio")

UTTERANCES: dict[str, str] = {
    "user_input_1.wav": "I want to transfer money.",
    "user_input_2.wav": "Checking.",
    "user_input_3.wav": "Savings.",
    "user_input_4.wav": "Five hundred dollars.",
    "user_input_5.wav": "Yes, please.",
}


async def main() -> None:
    from services.speechmatics_service import SpeechmaticsService, SpeechmaticsTTSError

    try:
        tts = SpeechmaticsService()
    except ValueError as exc:
        print(f"✗ {exc}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Generating user audio files via Speechmatics TTS")
    print("  Voice  : megan  (US female — Alex Chen)")
    print(f"  Output : {OUTPUT_DIR.resolve()}")
    print("=" * 60)

    for filename, text in UTTERANCES.items():
        print(f"  Generating {filename!r}  →  {text!r}")
        try:
            audio_bytes = await tts.synthesize(text, agent_role="caller")
            output_path = OUTPUT_DIR / filename
            output_path.write_bytes(audio_bytes)
            print(f"    ✓ Saved ({len(audio_bytes):,} bytes) → {output_path}")
        except SpeechmaticsTTSError as exc:
            print(f"    ✗ TTS error: {exc}")
            sys.exit(1)

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