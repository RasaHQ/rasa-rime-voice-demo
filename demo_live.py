# demo_live.py
import asyncio
import os
import io
import time
import sys
from pathlib import Path
from dotenv import load_dotenv
import aiohttp
from pydub import AudioSegment
from pydub.playback import play

# Rich UI Imports
from rich.console import Console, Group
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich import box

# Load env variables
load_dotenv()
console = Console()

# Configuration
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"
RIME_API_KEY = os.getenv("RIME_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
AUDIO_DIR = Path("tests/audio")

# The Story Script
CONVERSATION_STEPS = [
    {"file": "user_input_1.wav", "label": "Transfer Request"},
    {"file": "user_input_2.wav", "label": "Account Selection"},
    {"file": "user_input_3.wav", "label": "Account Destination"},
    {"file": "user_input_4.wav", "label": "Amount"},
    {"file": "user_input_5.wav", "label": "Confirmation"},
]

def make_layout():
    """Define the 3-section layout: Header, Chat History, Status Footer."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="status", size=3),
    )
    return layout

async def play_audio_data(audio_bytes: bytes):
    """Play raw audio bytes."""
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
        play(audio)
    except Exception as e:
        console.print(f"[red]Audio Error: {e}[/red]")

async def deepgram_transcribe(audio_path: Path) -> str:
    """Send audio to Deepgram."""
    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true"
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": "audio/wav"}
    
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=audio_data) as resp:
            data = await resp.json()
            # Handle potential Deepgram errors gracefully
            if 'results' in data:
                return data['results']['channels'][0]['alternatives'][0]['transcript']
            return "[Error: Transcribe Failed]"

async def rime_tts(text: str) -> bytes:
    """Send text to Rime."""
    url = "https://users.rime.ai/v1/rime-tts"
    headers = {
        "Authorization": f"Bearer {RIME_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "speaker": "cove", 
        "modelId": "mistv2",
        "speedAlpha": 1.0,
        "reduceLatency": True 
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            import base64
            if 'audioContent' in data:
                return base64.b64decode(data['audioContent'])
            return b""

async def run_demo():
    layout = make_layout()
    
    # Header Styling
    header_text = Text("🎁 Unwrap the Future: Voice Orchestration", style="bold white on magenta", justify="center")
    layout["header"].update(Panel(header_text, style="magenta"))
    
    # Store full history here
    full_history = []
    
    # CONFIG: How many chat bubbles to show at once?
    # Adjust this based on your screen size (6 is usually safe for standard terminals)
    MAX_VISIBLE_BUBBLES = 6

    def update_chat_view():
        """Helper to render only the latest messages."""
        # Slice to get only the last N items
        visible_history = full_history[-MAX_VISIBLE_BUBBLES:]
        layout["main"].update(
            Panel(
                Group(*visible_history), 
                title="Conversation Log", 
                border_style="white",
                padding=(1, 1)
            )
        )

    with Live(layout, refresh_per_second=10, screen=True) as live:
        
        for step in CONVERSATION_STEPS:
            audio_path = AUDIO_DIR / step['file']
            
            # --- STATE: USER SPEAKING ---
            status_text = f"🔊 User is speaking... [{step['label']}]"
            layout["status"].update(Panel(Text(status_text, style="bold cyan"), title="Status", border_style="cyan"))
            
            # Play user audio
            play(AudioSegment.from_wav(str(audio_path)))
            
            # --- STATE: TRANSCRIBING ---
            layout["status"].update(Panel(Text("⚡ Deepgram Transcribing...", style="bold yellow"), title="Status", border_style="yellow"))
            transcript = await deepgram_transcribe(audio_path)
            
            # Add User Message
            user_panel = Align.left(
                Panel(
                    Text(transcript, style="bright_white"),
                    title="User",
                    style="cyan",
                    box=box.ROUNDED,
                    padding=(1, 2),
                    width=60
                )
            )
            full_history.append(user_panel)
            update_chat_view()  # <--- FORCE SCROLL UPDATE
            
            # --- STATE: RASA THINKING ---
            layout["status"].update(Panel(Text("🧠 Rasa Thinking...", style="bold green"), title="Status", border_style="green"))
            
            async with aiohttp.ClientSession() as session:
                async with session.post(RASA_URL, json={"sender": "demo-user", "message": transcript}) as resp:
                    bot_responses = await resp.json()
            
            # --- STATE: AGENT SPEAKING ---
            for response in bot_responses:
                if 'text' in response:
                    agent_text = response['text']
                    
                    # Add Agent Message
                    agent_panel = Align.right(
                        Panel(
                            Text(agent_text, style="bright_white"),
                            title="Agent",
                            style="green",
                            box=box.ROUNDED,
                            padding=(1, 2),
                            width=60
                        )
                    )
                    full_history.append(agent_panel)
                    update_chat_view()  # <--- FORCE SCROLL UPDATE
                    
                    layout["status"].update(Panel(Text("🗣️ Rime Generating & Speaking...", style="bold magenta"), title="Status", border_style="magenta"))
                    
                    # Generate and Play
                    audio_bytes = await rime_tts(agent_text)
                    await play_audio_data(audio_bytes)

            time.sleep(0.5) 

        layout["status"].update(Panel(Text("✨ Demo Complete", style="bold white on green"), title="Status", border_style="green"))
        await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        sys.exit(0)