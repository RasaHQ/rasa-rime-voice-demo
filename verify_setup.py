#!/usr/bin/env python3
# === QV-LLM:BEGIN ===
# path: verify_setup.py
# role: module
# neighbors: demo_live.py, generate_user_audio.py
# exports: ok, warn, fail, section, hint, check_python_version, check_env_var, check_module (+2 more)
# git_branch: chore/updateLatest
# git_commit: fcce488
# === QV-LLM:END ===

"""
verify_setup.py — Pre-flight diagnostics for the voice demo.

Checks everything required before running the demo:
  - Environment variables (API keys)
  - Python dependencies
  - External service connectivity (Deepgram, Rime, Rasa)
  - Generated audio files

Usage:
    make verify
    # or directly:
    python verify_setup.py
"""

import asyncio
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}  ✓ {msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  ⚠ {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"{RED}  ✗ {msg}{RESET}")


def section(title: str) -> None:
    print(f"\n{BLUE}{BOLD}{'─' * 60}{RESET}")
    print(f"{BLUE}{BOLD}  {title}{RESET}")
    print(f"{BLUE}{BOLD}{'─' * 60}{RESET}")


def hint(msg: str) -> None:
    print(f"      {YELLOW}{msg}{RESET}")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_python_version() -> bool:
    v = sys.version_info
    if v.major == 3 and v.minor in (10, 11):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
        return True
    fail(f"Python {v.major}.{v.minor} detected — requires 3.10 or 3.11")
    hint("Use pyenv or a compatible virtualenv.")
    return False


def check_env_var(name: str, label: str) -> bool:
    value = os.getenv(name)
    if value and f"your-{name.lower().replace('_', '-')}" not in value.lower():
        # Mask the key: show first 4 + last 4 characters
        masked = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
        ok(f"{label} ({name}={masked})")
        return True
    fail(f"{label} not set  ({name})")
    hint(f"Add {name}=your-key to your .env file.")
    return False


def check_module(module: str, label: str) -> bool:
    if importlib.util.find_spec(module) is not None:
        ok(label)
        return True
    fail(f"{label} ({module}) not installed")
    hint("Run: make install")
    return False


def check_config_file(path: str) -> bool:
    if Path(path).exists():
        ok(path)
        return True
    fail(f"{path} not found")
    return False


def check_audio_files() -> bool:
    audio_dir = Path("tests/audio")
    expected = [f"user_input_{i}.wav" for i in range(1, 6)]
    missing = [f for f in expected if not (audio_dir / f).exists()]
    if not missing:
        ok(f"Audio files present in {audio_dir}/")
        return True
    fail(f"Missing audio files: {', '.join(missing)}")
    hint("Run: make generate-audio")
    return False


async def check_deepgram(api_key: str | None) -> bool:
    if not api_key:
        fail("Deepgram: skipped (API key not set)")
        return False
    try:
        import aiohttp
        headers = {"Authorization": f"Token {api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.deepgram.com/v1/projects",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    ok("Deepgram API key is valid")
                    return True
                fail(f"Deepgram returned HTTP {resp.status}")
                hint("Check your DEEPGRAM_API_KEY.")
                return False
    except Exception as exc:
        fail(f"Deepgram unreachable: {exc}")
        hint("Check your internet connection.")
        return False


async def check_rime(api_key: str | None) -> bool:
    if not api_key:
        fail("Rime: skipped (API key not set)")
        return False
    try:
        import aiohttp
        import base64
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"text": "Test.", "speaker": "cove", "modelId": "mistv2"}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://users.rime.ai/v1/rime-tts",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    ok("Rime API key is valid")
                    return True
                fail(f"Rime returned HTTP {resp.status}")
                hint("Check your RIME_API_KEY.")
                return False
    except Exception as exc:
        fail(f"Rime unreachable: {exc}")
        hint("Check your internet connection.")
        return False


async def check_rasa() -> bool:
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:5005/",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    ok("Rasa server is running (port 5005)")
                    return True
                fail(f"Rasa returned HTTP {resp.status}")
                return False
    except Exception:
        warn("Rasa server not running — start it before the demo")
        hint("Run: make run-rasa  (in a separate terminal)")
        return False  # warning, not a hard failure for setup check


async def check_action_server() -> bool:
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:5055/health",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    ok("Action server is running (port 5055)")
                    return True
                fail(f"Action server returned HTTP {resp.status}")
                return False
    except Exception:
        warn("Action server not running — start it before the demo")
        hint("Run: make run-actions  (in a separate terminal)")
        return False  # warning, not a hard failure for setup check


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_checks() -> int:
    print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{BLUE}  Voice Demo — Pre-flight Diagnostics{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 60}{RESET}")

    errors = 0
    warnings = 0

    # ── Python ──────────────────────────────────────────────────────────────
    section("Python Environment")
    if not check_python_version():
        errors += 1

    # ── API Keys ─────────────────────────────────────────────────────────────
    section("API Keys  (.env)")
    rasa_ok = check_env_var("RASA_LICENSE", "Rasa Pro License")
    dg_key = os.getenv("DEEPGRAM_API_KEY")
    rime_key = os.getenv("RIME_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not check_env_var("DEEPGRAM_API_KEY", "Deepgram API Key"):
        errors += 1
    if not check_env_var("RIME_API_KEY", "Rime API Key"):
        errors += 1
    if not check_env_var("OPENAI_API_KEY", "OpenAI API Key"):
        errors += 1
    if not rasa_ok:
        errors += 1

    # ── Python Dependencies ──────────────────────────────────────────────────
    section("Python Dependencies")
    deps = [
        ("rasa", "Rasa Pro"),
        ("rasa_sdk", "Rasa SDK"),
        ("aiohttp", "aiohttp"),
        ("pydub", "pydub"),
        ("rich", "rich"),
        ("dotenv", "python-dotenv"),
    ]
    for module, label in deps:
        if not check_module(module, label):
            errors += 1

    # ── Config Files ─────────────────────────────────────────────────────────
    section("Project Config Files")
    config_files = [
        "config.yml",
        "credentials.yml",
        "domain.yml",
        "endpoints.yml",
        "data/flows.yml",
        ".env",
    ]
    for path in config_files:
        if not check_config_file(path):
            errors += 1

    # ── Audio Files ───────────────────────────────────────────────────────────
    section("Demo Audio Files")
    if not check_audio_files():
        errors += 1

    # ── External Service Connectivity ─────────────────────────────────────────
    section("External Service Connectivity")
    if not await check_deepgram(dg_key):
        errors += 1
    if not await check_rime(rime_key):
        errors += 1

    # ── Running Services (warnings only — not required at verify time) ─────────
    section("Running Services  (required at demo time)")
    rasa_running = await check_rasa()
    actions_running = await check_action_server()
    if not rasa_running:
        warnings += 1
    if not actions_running:
        warnings += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    if errors == 0 and warnings == 0:
        print(f"{GREEN}{BOLD}✓ All checks passed — ready to demo!{RESET}")
        print()
        print("  make run-actions   # Tab 1")
        print("  make run-rasa      # Tab 2")
        print("  make demo          # Tab 3")
    elif errors == 0:
        print(f"{YELLOW}{BOLD}⚠ Setup complete with {warnings} warning(s).{RESET}")
        print(f"{YELLOW}  Start the services above before running: make demo{RESET}")
    else:
        print(f"{RED}{BOLD}✗ {errors} error(s) found — fix them before running the demo.{RESET}")
        if warnings:
            print(f"{YELLOW}  Also {warnings} warning(s) noted above.{RESET}")
    print()

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_checks()))