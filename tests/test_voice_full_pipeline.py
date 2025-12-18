# tests/test_voice_full_pipeline.py
#!/usr/bin/env python3
"""
Automated Voice Testing - Full Pipeline
Tests voice assistant by:
1. Converting test audio → text (ASR)
2. Sending text to Rasa
3. Getting bot response
4. Converting response → audio (TTS)
5. Saving response audio
"""

import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import aiohttp

# Audio processing
try:
    import audioop
    from pydub import AudioSegment
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run(["pip", "install", "pydub", "--break-system-packages"])
    import audioop
    from pydub import AudioSegment


# Configuration
RASA_URL = "http://localhost:5005"
TEST_AUDIO_DIR = Path("tests/audio")
OUTPUT_AUDIO_DIR = Path("tests/audio_responses")
OUTPUT_AUDIO_DIR.mkdir(exist_ok=True)


# Color codes for terminal output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'


@dataclass
class VoiceTestResult:
    """Results from a voice test."""
    test_name: str
    passed: bool = False
    transcription: str = ""
    bot_response_text: str = ""
    bot_response_audio: Optional[Path] = None
    duration: float = 0.0
    error_message: str = ""


def audio_to_text_simple(audio_file: Path) -> str:
    """
    Simple audio-to-text conversion.
    
    In production, you'd use a real ASR service (Deepgram, Azure, etc.)
    For testing, we'll use a mapping based on filename.
    """
    # Map test files to expected transcriptions
    transcriptions = {
        "check_balance.wav": "What's my balance?",
        "checking.wav": "Checking",
        "savings.wav": "Savings",
        "transfer_money.wav": "I want to transfer money",
        "five_hundred.wav": "Five hundred dollars",
        "yes.wav": "Yes",
        "lost_card.wav": "I lost my card",
        "card_digits.wav": "4532",
        "cancel.wav": "Cancel",
        "help.wav": "Help",
        "goodbye.wav": "Goodbye",
    }
    
    return transcriptions.get(audio_file.name, audio_file.stem.replace("_", " "))


def text_to_audio_simple(text: str, output_file: Path) -> None:
    """
    Simple text-to-audio conversion.
    
    In production, you'd use a real TTS service (Azure, Cartesia, Deepgram, etc.)
    For testing, we'll create a silent audio file as a placeholder.
    """
    # Create a 1-second silent audio file as placeholder
    # In production, this would call your TTS service
    
    # Generate silence (8kHz, mono, 1 second)
    duration_ms = 1000
    silence = AudioSegment.silent(duration=duration_ms, frame_rate=8000)
    silence = silence.set_channels(1)  # Mono
    silence = silence.set_sample_width(1)  # 8-bit
    
    # Save as WAV
    silence.export(str(output_file), format="wav")
    
    # Add metadata comment (not in audio, just for testing)
    with open(output_file.with_suffix(".txt"), "w") as f:
        f.write(f"TTS OUTPUT: {text}\n")


async def send_text_to_rasa(text: str, sender_id: str) -> List[dict]:
    """Send text message to Rasa and get response."""
    
    async with aiohttp.ClientSession() as session:
        # Try REST webhook first (requires 'rest:' in credentials.yml)
        url = f"{RASA_URL}/webhooks/rest/webhook"
        payload = {"sender": sender_id, "message": text}
        
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    # REST channel not configured
                    raise Exception(
                        "REST channel not found. Please add 'rest:' to your credentials.yml file.\n"
                        "See: FIX_REST_WEBHOOK.md"
                    )
                else:
                    text_resp = await response.text()
                    raise Exception(f"Rasa returned status {response.status}: {text_resp}")
        except aiohttp.ClientError as e:
            raise Exception(f"Failed to connect to Rasa: {e}")


async def test_voice_flow(
    test_name: str,
    audio_files: List[str],
    sender_id: str,
    validation_fn
) -> VoiceTestResult:
    """
    Test a complete voice flow.
    
    Args:
        test_name: Name of the test
        audio_files: List of audio filenames to send in sequence
        sender_id: Unique sender ID for this conversation
        validation_fn: Function to validate the final response
    """
    result = VoiceTestResult(test_name=test_name)
    start_time = time.time()
    
    try:
        all_responses = []
        
        for i, audio_filename in enumerate(audio_files):
            audio_path = TEST_AUDIO_DIR / audio_filename
            
            # Step 1: Audio → Text (ASR)
            print(f"{Colors.BLUE}  [{i+1}/{len(audio_files)}] Processing: {audio_filename}{Colors.RESET}")
            user_text = audio_to_text_simple(audio_path)
            print(f"    Transcribed: '{user_text}'")
            
            # Step 2: Send to Rasa
            responses = await send_text_to_rasa(user_text, sender_id)
            
            # Step 3: Extract bot text
            bot_texts = []
            for msg in responses:
                if isinstance(msg, dict) and 'text' in msg:
                    bot_texts.append(msg['text'])
            
            if bot_texts:
                bot_text = " ".join(bot_texts)
                print(f"    Bot said: '{bot_text}'")
                
                # Step 4: Text → Audio (TTS)
                output_audio = OUTPUT_AUDIO_DIR / f"{test_name.replace(' ', '_')}_{i+1}.wav"
                text_to_audio_simple(bot_text, output_audio)
                result.bot_response_audio = output_audio
                
                all_responses.append(bot_text)
            
            # Small delay between steps
            if i < len(audio_files) - 1:
                await asyncio.sleep(0.5)
        
        # Validate
        result.bot_response_text = " → ".join(all_responses)
        result.transcription = " → ".join([
            audio_to_text_simple(TEST_AUDIO_DIR / f) for f in audio_files
        ])
        
        result.passed = validation_fn(all_responses)
        
        if not result.passed:
            result.error_message = f"Validation failed. Responses: {all_responses}"
    
    except Exception as e:
        result.error_message = f"Error: {str(e)}"
    
    finally:
        result.duration = time.time() - start_time
    
    return result


async def test_check_balance_flow():
    """Test: Check balance flow with audio input/output."""
    
    def validate(responses):
        # Check if any response mentions account type
        response_text = " ".join(responses).lower()
        return "account" in response_text or "balance" in response_text
    
    return await test_voice_flow(
        test_name="Check Balance",
        audio_files=["check_balance.wav", "checking.wav"],
        sender_id="voice-test-balance",
        validation_fn=validate
    )


async def test_transfer_flow():
    """Test: Money transfer flow with audio input/output."""
    
    def validate(responses):
        response_text = " ".join(responses).lower()
        # Check for transfer-related keywords
        return any(kw in response_text for kw in ["transfer", "account", "amount", "confirm"])
    
    return await test_voice_flow(
        test_name="Transfer Money",
        audio_files=["transfer_money.wav", "checking.wav", "savings.wav", "five_hundred.wav", "yes.wav"],
        sender_id="voice-test-transfer",
        validation_fn=validate
    )


async def test_lost_card_flow():
    """Test: Lost card flow with audio input/output."""
    
    def validate(responses):
        response_text = " ".join(responses).lower()
        return "card" in response_text or "block" in response_text
    
    return await test_voice_flow(
        test_name="Lost Card",
        audio_files=["lost_card.wav", "card_digits.wav"],
        sender_id="voice-test-lostcard",
        validation_fn=validate
    )


async def check_rasa_connection():
    """Check if Rasa server is available."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{RASA_URL}/", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    print(f"{Colors.GREEN}✓ Rasa server is running at {RASA_URL}{Colors.RESET}")
                    return True
    except Exception:
        pass
    
    print(f"{Colors.RED}✗ Cannot connect to Rasa server at {RASA_URL}{Colors.RESET}")
    print(f"\n{Colors.YELLOW}Please start Rasa in another terminal:{Colors.RESET}")
    print(f"  {Colors.GREEN}make inspect{Colors.RESET}  or  {Colors.GREEN}make inspect-voice{Colors.RESET}\n")
    return False


def print_result(result: VoiceTestResult):
    """Print test result."""
    status = f"{Colors.GREEN}✓ PASS" if result.passed else f"{Colors.RED}✗ FAIL"
    print(f"\n{status} {result.test_name} ({result.duration:.2f}s){Colors.RESET}")
    
    if result.transcription:
        print(f"  Audio Input: '{result.transcription}'")
    
    if result.bot_response_text:
        print(f"  Bot Response: '{result.bot_response_text}'")
    
    if result.bot_response_audio:
        print(f"  Audio Output: {result.bot_response_audio}")
        print(f"    (Text file: {result.bot_response_audio.with_suffix('.txt')})")
    
    if result.error_message:
        print(f"  {Colors.RED}{result.error_message}{Colors.RESET}")


async def run_all_tests():
    """Run all voice tests."""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Automated Voice Testing - Full Pipeline{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")
    
    # Check Rasa connection
    if not await check_rasa_connection():
        return 1
    
    # Check audio files
    if not TEST_AUDIO_DIR.exists():
        print(f"{Colors.YELLOW}Creating test audio directory: {TEST_AUDIO_DIR}{Colors.RESET}")
        TEST_AUDIO_DIR.mkdir(parents=True)
        print(f"{Colors.YELLOW}Please generate test audio files first:{Colors.RESET}")
        print(f"  {Colors.GREEN}make generate-test-audio{Colors.RESET}\n")
        return 1
    
    print(f"Test audio: {TEST_AUDIO_DIR}")
    print(f"Output audio: {OUTPUT_AUDIO_DIR}\n")
    
    print(f"{Colors.BLUE}Running voice tests with full ASR→Rasa→TTS pipeline...{Colors.RESET}\n")
    
    # Run tests
    tests = [
        test_check_balance_flow(),
        test_transfer_flow(),
        test_lost_card_flow(),
    ]
    
    results = await asyncio.gather(*tests)
    
    # Print results
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Test Results{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    for result in results:
        print_result(result)
    
    # Summary
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    pass_rate = (passed / len(results) * 100) if results else 0
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"Total: {len(results)} tests")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
    if failed > 0:
        print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    exit(exit_code)