# scripts/generate_user_audio.py
import asyncio
import os
import aiohttp
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

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
    headers = {"Authorization": f"Bearer {os.getenv('RIME_API_KEY')}", "Content-Type": "application/json"}
    payload = {"text": text, "speaker": SPEAKER, "modelId": "mistv2"}
    
    print(f"Generating {filename} ({text})...")
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            audio_bytes = base64.b64decode(data['audioContent'])
            
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            with open(OUTPUT_DIR / filename, "wb") as f:
                f.write(audio_bytes)

async def main():
    tasks = [generate(f, t) for f, t in TRANSCRIPTS.items()]
    await asyncio.gather(*tasks)
    print("Done! User audio ready for demo.")

if __name__ == "__main__":
    asyncio.run(main())