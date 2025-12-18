# scripts/generate_user_audio.py
import asyncio
import os
import aiohttp
import base64
from pathlib import Path
from dotenv import load_dotenv

# 1. Force load the .env file from the project root
# This ensures it works even if 'make' doesn't export variables correctly
project_root = Path(__file__).parent.parent
load_dotenv(dotenv_path=project_root / ".env")

# 2. Debug the Key (Safety Check)
RIME_KEY = os.getenv("RIME_API_KEY")
if not RIME_KEY:
    print("❌ CRITICAL: RIME_API_KEY is missing/None.")
    exit(1)
else:
    # Print first/last 4 chars to verify it's loaded without leaking it
    masked_key = f"{RIME_KEY[:4]}...{RIME_KEY[-4:]}"
    print(f"🔑 Loaded Rime Key: {masked_key} (Length: {len(RIME_KEY)})")

# "User" Voice Configuration
SPEAKER = "abbie" 
OUTPUT_DIR = Path("tests/audio")

TRANSCRIPTS = {
    "user_input_1.wav": "I want to transfer money.",
    "user_input_2.wav": "Checking.",
    "user_input_3.wav": "Savings.",
    "user_input_4.wav": "Five hundred dollars.",
    "user_input_5.wav": "Yes, please."
}

async def generate(filename, text):
    url = "https://users.rime.ai/v1/rime-tts"
    headers = {
        "Authorization": f"Bearer {RIME_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "speaker": SPEAKER,
        "modelId": "mistv2"
    }
    
    print(f"Generating {filename}...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                print(f"  ❌ Error {resp.status}: {error_text}")
                return

            data = await resp.json()
            if 'audioContent' in data:
                audio_bytes = base64.b64decode(data['audioContent'])
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                with open(OUTPUT_DIR / filename, "wb") as f:
                    f.write(audio_bytes)
                print(f"  ✅ Saved")
            else:
                print(f"  ⚠️ Unexpected response: {data}")

async def main():
    tasks = [generate(f, t) for f, t in TRANSCRIPTS.items()]
    await asyncio.gather(*tasks)
    print("\nDone! User audio ready for demo.")

if __name__ == "__main__":
    asyncio.run(main())