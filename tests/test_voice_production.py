# tests/test_voice_production.py
#!/usr/bin/env python3
"""
Production Voice Testing with Real ASR/TTS
Uses actual speech services (Azure, Deepgram, etc.) for testing
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

import aiohttp


# Color codes for terminal output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'


# ============================================================================
# ASR (Speech-to-Text) Integration
# ============================================================================

async def transcribe_audio_azure(audio_file: Path) -> str:
    """Transcribe audio using Azure Speech Service."""
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        raise ImportError("Install: pip install azure-cognitiveservices-speech")
    
    api_key = os.getenv("AZURE_SPEECH_API_KEY")
    region = os.getenv("AZURE_SPEECH_REGION", "eastus")
    
    if not api_key:
        raise ValueError("AZURE_SPEECH_API_KEY environment variable not set")
    
    speech_config = speechsdk.SpeechConfig(subscription=api_key, region=region)
    audio_config = speechsdk.audio.AudioConfig(filename=str(audio_file))
    
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config
    )
    
    result = speech_recognizer.recognize_once()
    
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        raise Exception(f"No speech recognized in {audio_file}")
    else:
        raise Exception(f"ASR failed: {result.reason}")


async def transcribe_audio_deepgram(audio_file: Path) -> str:
    """Transcribe audio using Deepgram API."""
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise ValueError("DEEPGRAM_API_KEY environment variable not set")
    
    url = "https://api.deepgram.com/v1/listen"
    
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/wav"
    }
    
    params = {
        "model": "nova-2-general",
        "language": "en",
        "smart_format": "true"
    }
    
    with open(audio_file, "rb") as audio:
        audio_data = audio.read()
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, params=params, data=audio_data) as response:
            if response.status == 200:
                data = await response.json()
                transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
                return transcript
            else:
                text = await response.text()
                raise Exception(f"Deepgram API error: {response.status} - {text}")


# ============================================================================
# TTS (Text-to-Speech) Integration
# ============================================================================

async def synthesize_speech_azure(text: str, output_file: Path) -> None:
    """Convert text to speech using Azure TTS."""
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        raise ImportError("Install: pip install azure-cognitiveservices-speech")
    
    api_key = os.getenv("AZURE_SPEECH_API_KEY")
    region = os.getenv("AZURE_SPEECH_REGION", "eastus")
    
    if not api_key:
        raise ValueError("AZURE_SPEECH_API_KEY environment variable not set")
    
    speech_config = speechsdk.SpeechConfig(subscription=api_key, region=region)
    speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
    
    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output_file))
    
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=audio_config
    )
    
    result = synthesizer.speak_text_async(text).get()
    
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise Exception(f"TTS failed: {result.reason}")


async def synthesize_speech_rime(text: str, output_file: Path) -> None:
    """Convert text to speech using Rime TTS."""
    api_key = os.getenv("RIME_API_KEY")
    if not api_key:
        raise ValueError("RIME_API_KEY environment variable not set")
    
    url = "https://users.rime.ai/v1/rime-tts"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": text,
        "speaker": "cove",
        "modelId": "mist",
        "speedAlpha": 1.0,
        "reduceLatency": False
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                # Rime returns JSON with audio data
                data = await response.json()
                
                # The response contains base64-encoded audio or URL
                if 'audioContent' in data:
                    # Base64 encoded audio
                    import base64
                    audio_bytes = base64.b64decode(data['audioContent'])
                    output_file.write_bytes(audio_bytes)
                    print(f"    Decoded {len(audio_bytes)} bytes from base64")
                    
                elif 'audio' in data:
                    # Might be base64 in 'audio' field
                    import base64
                    audio_bytes = base64.b64decode(data['audio'])
                    output_file.write_bytes(audio_bytes)
                    print(f"    Decoded {len(audio_bytes)} bytes from base64")
                    
                elif 'url' in data:
                    # Audio is at a URL
                    audio_url = data['url']
                    async with session.get(audio_url) as audio_response:
                        audio_bytes = await audio_response.read()
                        output_file.write_bytes(audio_bytes)
                        print(f"    Downloaded {len(audio_bytes)} bytes from URL")
                        
                else:
                    # Unknown format - show what we got
                    print(f"    Rime response keys: {list(data.keys())}")
                    print(f"    Response sample: {str(data)[:200]}")
                    raise Exception(f"Unexpected Rime response format. Keys: {list(data.keys())}")
                    
            else:
                text_resp = await response.text()
                raise Exception(f"Rime TTS error: {response.status} - {text_resp}")


async def synthesize_speech_deepgram(text: str, output_file: Path) -> None:
    """Convert text to speech using Deepgram TTS."""
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise ValueError("DEEPGRAM_API_KEY environment variable not set")
    
    url = "https://api.deepgram.com/v1/speak"
    
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }
    
    params = {
        "model": "aura-2-andromeda-en"
    }
    
    payload = {
        "text": text
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, params=params, json=payload) as response:
            if response.status == 200:
                audio_data = await response.read()
                output_file.write_bytes(audio_data)
            else:
                text_resp = await response.text()
                raise Exception(f"Deepgram TTS error: {response.status} - {text_resp}")


# ============================================================================
# Auto-detect which service to use
# ============================================================================

async def transcribe_audio(audio_file: Path) -> str:
    """Auto-detect and use available ASR service."""
    
    if os.getenv("DEEPGRAM_API_KEY"):
        print(f"  Using Deepgram ASR")
        return await transcribe_audio_deepgram(audio_file)
    elif os.getenv("AZURE_SPEECH_API_KEY"):
        print(f"  Using Azure ASR")
        return await transcribe_audio_azure(audio_file)
    else:
        raise ValueError(
            "No ASR service configured. Set one of:\n"
            "  - DEEPGRAM_API_KEY\n"
            "  - AZURE_SPEECH_API_KEY"
        )


async def synthesize_speech(text: str, output_file: Path) -> None:
    """Auto-detect and use available TTS service."""
    
    # Priority: Rime (matches Rasa config) > Deepgram > Azure
    if os.getenv("RIME_API_KEY"):
        print(f"  Using Rime TTS")
        await synthesize_speech_rime(text, output_file)
    elif os.getenv("DEEPGRAM_API_KEY"):
        print(f"  Using Deepgram TTS")
        await synthesize_speech_deepgram(text, output_file)
    elif os.getenv("AZURE_SPEECH_API_KEY"):
        print(f"  Using Azure TTS")
        await synthesize_speech_azure(text, output_file)
    else:
        raise ValueError(
            "No TTS service configured. Set one of:\n"
            "  - RIME_API_KEY (recommended - matches Rasa config)\n"
            "  - DEEPGRAM_API_KEY\n"
            "  - AZURE_SPEECH_API_KEY"
        )


# ============================================================================
# Example usage
# ============================================================================

async def test_check_balance_flow():
    """Test: Complete check balance conversation flow."""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Test: Check Balance Flow{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")
    
    sender_id = "voice-test-balance"
    audio_dir = Path("tests/audio")
    output_dir = Path("tests/audio_responses/check_balance")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define the conversation flow
    conversation = [
        ("check_balance.wav", "What's my balance?"),
        ("checking.wav", "Checking"),
    ]
    
    async with aiohttp.ClientSession() as session:
        for turn, (audio_file, expected_text) in enumerate(conversation, 1):
            print(f"{Colors.BLUE}Turn {turn}/{len(conversation)}{Colors.RESET}")
            
            # 1. Transcribe audio
            audio_path = audio_dir / audio_file
            print(f"  1. Transcribing: {audio_file}")
            user_text = await transcribe_audio(audio_path)
            print(f"     User said: '{user_text}'\n")
            
            # 2. Send to Rasa
            print(f"  2. Sending to Rasa...")
            response = await session.post(
                "http://localhost:5005/webhooks/rest/webhook",
                json={"sender": sender_id, "message": user_text}
            )
            
            if response.status != 200:
                print(f"     {Colors.RED}Error: {response.status}{Colors.RESET}\n")
                return False
            
            bot_responses = await response.json()
            bot_text = " ".join([msg['text'] for msg in bot_responses if 'text' in msg])
            print(f"     Bot said: '{bot_text}'\n")
            
            # 3. Synthesize speech
            if bot_text:
                print(f"  3. Synthesizing speech...")
                output_file = output_dir / f"turn_{turn}_response.wav"
                await synthesize_speech(bot_text, output_file)
                print(f"     Saved: {output_file}\n")
            
            # Small delay between turns
            if turn < len(conversation):
                await asyncio.sleep(0.5)
    
    print(f"{Colors.GREEN}✓ Check Balance flow completed{Colors.RESET}")
    print(f"{Colors.GREEN}  Audio responses saved to: {output_dir}{Colors.RESET}\n")
    return True


async def test_transfer_money_flow():
    """Test: Complete money transfer conversation flow."""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Test: Transfer Money Flow{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")
    
    sender_id = "voice-test-transfer"
    audio_dir = Path("tests/audio")
    output_dir = Path("tests/audio_responses/transfer_money")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define the conversation flow
    conversation = [
        ("transfer_money.wav", "I want to transfer money"),
        ("checking.wav", "Checking"),
        ("savings.wav", "Savings"),
        ("five_hundred.wav", "Five hundred dollars"),
        ("yes.wav", "Yes"),
    ]
    
    async with aiohttp.ClientSession() as session:
        for turn, (audio_file, expected_text) in enumerate(conversation, 1):
            print(f"{Colors.BLUE}Turn {turn}/{len(conversation)}{Colors.RESET}")
            
            # 1. Transcribe audio
            audio_path = audio_dir / audio_file
            print(f"  1. Transcribing: {audio_file}")
            user_text = await transcribe_audio(audio_path)
            print(f"     User said: '{user_text}'\n")
            
            # 2. Send to Rasa
            print(f"  2. Sending to Rasa...")
            response = await session.post(
                "http://localhost:5005/webhooks/rest/webhook",
                json={"sender": sender_id, "message": user_text}
            )
            
            if response.status != 200:
                print(f"     {Colors.RED}Error: {response.status}{Colors.RESET}\n")
                return False
            
            bot_responses = await response.json()
            bot_text = " ".join([msg['text'] for msg in bot_responses if 'text' in msg])
            
            if bot_text:
                print(f"     Bot said: '{bot_text}'\n")
                
                # 3. Synthesize speech
                print(f"  3. Synthesizing speech...")
                output_file = output_dir / f"turn_{turn}_response.wav"
                await synthesize_speech(bot_text, output_file)
                print(f"     Saved: {output_file}\n")
            else:
                print(f"     {Colors.YELLOW}(Bot sent no text response){Colors.RESET}\n")
            
            # Small delay between turns
            if turn < len(conversation):
                await asyncio.sleep(0.5)
    
    print(f"{Colors.GREEN}✓ Transfer Money flow completed{Colors.RESET}")
    print(f"{Colors.GREEN}  Audio responses saved to: {output_dir}{Colors.RESET}\n")
    return True


async def test_lost_card_flow():
    """Test: Complete lost card conversation flow."""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Test: Lost Card Flow{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")
    
    sender_id = "voice-test-lostcard"
    audio_dir = Path("tests/audio")
    output_dir = Path("tests/audio_responses/lost_card")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define the conversation flow
    conversation = [
        ("lost_card.wav", "I lost my card"),
        ("card_digits.wav", "4532"),
    ]
    
    async with aiohttp.ClientSession() as session:
        for turn, (audio_file, expected_text) in enumerate(conversation, 1):
            print(f"{Colors.BLUE}Turn {turn}/{len(conversation)}{Colors.RESET}")
            
            # 1. Transcribe audio
            audio_path = audio_dir / audio_file
            print(f"  1. Transcribing: {audio_file}")
            user_text = await transcribe_audio(audio_path)
            print(f"     User said: '{user_text}'\n")
            
            # 2. Send to Rasa
            print(f"  2. Sending to Rasa...")
            response = await session.post(
                "http://localhost:5005/webhooks/rest/webhook",
                json={"sender": sender_id, "message": user_text}
            )
            
            if response.status != 200:
                print(f"     {Colors.RED}Error: {response.status}{Colors.RESET}\n")
                return False
            
            bot_responses = await response.json()
            bot_text = " ".join([msg['text'] for msg in bot_responses if 'text' in msg])
            print(f"     Bot said: '{bot_text}'\n")
            
            # 3. Synthesize speech
            if bot_text:
                print(f"  3. Synthesizing speech...")
                output_file = output_dir / f"turn_{turn}_response.wav"
                await synthesize_speech(bot_text, output_file)
                print(f"     Saved: {output_file}\n")
            
            # Small delay between turns
            if turn < len(conversation):
                await asyncio.sleep(0.5)
    
    print(f"{Colors.GREEN}✓ Lost Card flow completed{Colors.RESET}")
    print(f"{Colors.GREEN}  Audio responses saved to: {output_dir}{Colors.RESET}\n")
    return True


async def run_all_tests():
    """Run all conversation flow tests."""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Voice Pipeline Testing - Complete Conversations{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")
    
    # Check if test audio exists
    audio_dir = Path("tests/audio")
    if not audio_dir.exists() or not list(audio_dir.glob("*.wav")):
        print(f"{Colors.RED}✗ Test audio files not found{Colors.RESET}")
        print(f"\nPlease generate test audio first:")
        print(f"  {Colors.GREEN}make generate-test-audio{Colors.RESET}\n")
        return 1
    
    print(f"Test audio directory: {audio_dir}")
    print(f"Available files: {len(list(audio_dir.glob('*.wav')))} WAV files\n")
    
    # Run all test flows
    results = []
    
    try:
        results.append(await test_check_balance_flow())
        results.append(await test_transfer_money_flow())
        results.append(await test_lost_card_flow())
    except Exception as e:
        print(f"\n{Colors.RED}✗ Test failed with error:{Colors.RESET}")
        print(f"  {str(e)}\n")
        return 1
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Test Summary{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"Total flows tested: {total}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
    
    if passed < total:
        print(f"{Colors.RED}Failed: {total - passed}{Colors.RESET}")
    
    print(f"\n{Colors.GREEN}All conversation audio saved to: tests/audio_responses/{Colors.RESET}")
    print(f"\nYou can now:")
    print(f"  • Listen to bot responses in tests/audio_responses/")
    print(f"  • Verify conversation quality manually")
    print(f"  • Use these for training or documentation\n")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())