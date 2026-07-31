#!/usr/bin/env python3
"""
Termux AI Bot
-------------
Ask it to do something in plain English, it asks an AI (Claude or an
OpenRouter model) to write a Termux-compatible bash script, shows you
the script, and (only after you confirm) runs it.

Setup on your phone (Termux):
    pkg update && pkg upgrade
    pkg install python
    pip install requests

    # Choose ONE provider:

    # Option A: Anthropic (Claude) directly
    export AI_PROVIDER="anthropic"
    export ANTHROPIC_API_KEY="sk-ant-...."

    # Option B: OpenRouter (many free models)
    export AI_PROVIDER="openrouter"
    export OPENROUTER_API_KEY="sk-or-v1-...."
    export OPENROUTER_MODEL="openrouter/free"  # optional override

    python aibot.py

Usage:
    python aibot.py "play an online radio station"
    # or run with no args to enter interactive menu mode
"""

import os
import sys
import subprocess
import re
import json
import requests

PROVIDER = os.environ.get("AI_PROVIDER", "anthropic").strip().lower()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")

SCRIPT_PATH = os.path.expanduser("~/aibot_last_script.sh")

SYSTEM_PROMPT = """You write short bash scripts that run inside Termux on Android.

Rules:
- Output ONLY a single bash code block. No explanation before or after.
- The script must be self-contained and runnable on Termux (assume `pkg` package manager, not `apt`).
- If a package is needed (e.g. mpv, ffmpeg, curl, termux-api tools), include a `pkg install -y <package>` line at the top, but skip re-installing if already present (use `command -v` checks).
- Prefer well-known, reliable, legal public streams/tools for tasks like radio, weather, etc.
- Never include destructive commands (no rm -rf /, no formatting storage, no modifying system files).
- Keep it as simple as possible while doing the job well.
"""

FAVORITES = {
    "1": "play an online radio station",
    "2": "check the weather using a terminal weather tool",
    "3": "start an FTP server on the Download folder using pyftpdlib",
}


def validate_config() -> None:
    """Validate the right API key is set for the chosen provider."""
    if PROVIDER == "anthropic":
        if not ANTHROPIC_API_KEY:
            print("ERROR: AI_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set.")
            print('  export ANTHROPIC_API_KEY="sk-ant-...."')
            sys.exit(1)
    elif PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            print("ERROR: AI_PROVIDER=openrouter but OPENROUTER_API_KEY is not set.")
            print('  export OPENROUTER_API_KEY="sk-or-v1-...."')
            sys.exit(1)
    else:
        print(f"ERROR: Unknown AI_PROVIDER '{PROVIDER}'. Use 'anthropic' or 'openrouter'.")
        sys.exit(1)


def ask_claude(user_request: str) -> str:
    """Send request to Anthropic's API and return the response text."""
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_request}],
    }
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        resp = requests.post(ANTHROPIC_API_URL, headers=headers, data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks)
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        sys.exit(1)


def ask_openrouter(user_request: str) -> str:
    """Send request to OpenRouter's API and return the response text."""
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ],
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(OPENROUTER_API_URL, headers=headers, data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            print(f"Unexpected response from OpenRouter: {data}")
            sys.exit(1)
        return choices[0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        sys.exit(1)


def ask_ai(user_request: str) -> str:
    """Dispatch to the configured provider."""
    validate_config()
    if PROVIDER == "anthropic":
        return ask_claude(user_request)
    return ask_openrouter(user_request)


def extract_script(ai_text: str) -> str:
    """Extract bash script from AI's response text."""
    match = re.search(r"```(?:bash|sh)?\n(.*?)```", ai_text, re.DOTALL)
    if not match:
        match = re.search(r"```\n(.*?)```", ai_text, re.DOTALL)
    return match.group(1).strip() if match else ai_text.strip()


def show_menu() -> str:
    print("\n=== Termux AI Bot ===")
    print("1) Play online radio")
    print("2) Check weather")
    print("3) Start FTP server")
    print("4) Custom request")
    print("5) Exit")
    return input("> ").strip()


def main():
    if len(sys.argv) > 1:
        request = " ".join(sys.argv[1:])
    else:
        choice = show_menu()
        if choice == "5":
            print("Bye!")
            return
        elif choice == "4":
            request = input("What do you want your Termux bot to do?\n> ").strip()
        elif choice in FAVORITES:
            request = FAVORITES[choice]
        else:
            print("Invalid choice.")
            return

    if not request:
        print("No request given, exiting.")
        return

    print(f"\n[Asking {PROVIDER} to write the script...]\n")
    ai_reply = ask_ai(request)
    script = extract_script(ai_reply)

    print("----- Generated script -----")
    print(script)
    print("-----------------------------\n")

    with open(SCRIPT_PATH, "w") as f:
        f.write(script)
    os.chmod(SCRIPT_PATH, 0o755)

    run_choice = input("Run this script now? [y/N]: ").strip().lower()
    if run_choice == "y":
        print("\n[Running...]\n")
        subprocess.run(["bash", SCRIPT_PATH])
    else:
        print(f"Not run. Saved at {SCRIPT_PATH} — you can review/run it manually with:")
        print(f"  bash {SCRIPT_PATH}")


if __name__ == "__main__":
    main()
