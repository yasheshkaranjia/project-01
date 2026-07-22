#!/usr/bin/env python3
"""
Termux AI Bot
-------------
Ask it to do something in plain English, it asks Claude to write a
Termux-compatible bash script, shows you the script, and (only after
you confirm) runs it.

Setup on your phone (Termux):
    pkg update && pkg upgrade
    pkg install python
    pip install requests
    export ANTHROPIC_API_KEY="sk-ant-...."      # put your real key here
    python aibot.py

Usage:
    python aibot.py "play an online radio station"
    # or run with no args to enter interactive mode
"""

import os
import sys
import subprocess
import re
import json
import requests

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"
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

def validate_api_key() -> None:
    """Validate the API key is set before making requests."""
    if not API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable first.")
        print('  export ANTHROPIC_API_KEY="sk-ant-...."')
        sys.exit(1)

def get_api_headers() -> dict:
    """Get headers for Claude API request."""
    return {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

def ask_claude(user_request: str) -> str:
    """Send request to Claude API and return the response text.
    
    Args:
        user_request: The user's request in plain English
        
    Returns:
        The raw text response from Claude
        
    Raises:
        requests.exceptions.RequestException: If API request fails
    """
    validate_api_key()
    payload = create_api_payload(user_request)
    headers = get_api_headers()

    try:
        resp = requests.post(API_URL, headers=headers, data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks)
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        sys.exit(1)


def extract_script(ai_text: str) -> str:
    """Extract bash script from AI's response text.
    
    Args:
        ai_text: Raw text response from Claude
        
    Returns:
        Extracted bash script content
        
    Note:
        If no code block markers are found, assumes entire response is the script
    """
    # Try to find code block with optional language specifier
    match = re.search(r"```(?:bash|sh)?\n(.*?)```", ai_text, re.DOTALL)
    if not match:
        # Fallback: look for unmarked code block
        match = re.search(r"```\n(.*?)```", ai_text, re.DOTALL)
    
    return match.group(1).strip() if match else ai_text.strip()


def main():
    if len(sys.argv) > 1:
        request = " ".join(sys.argv[1:])
    else:
        request = input("What do you want your Termux bot to do?\n> ").strip()

    if not request:
        print("No request given, exiting.")
        return

    print("\n[Asking AI to write the script...]\n")
    ai_reply = ask_claude(request)
    script = extract_script(ai_reply)

    print("----- Generated script -----")
    print(script)
    print("-----------------------------\n")

    with open(SCRIPT_PATH, "w") as f:
        f.write(script)
    os.chmod(SCRIPT_PATH, 0o755)

    choice = input("Run this script now? [y/N]: ").strip().lower()
    if choice == "y":
        print("\n[Running...]\n")
        subprocess.run(["bash", SCRIPT_PATH])
    else:
        print(f"Not run. Saved at {SCRIPT_PATH} — you can review/run it manually with:")
        print(f"  bash {SCRIPT_PATH}")


if __name__ == "__main__":
    main()
