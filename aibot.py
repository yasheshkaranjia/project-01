#!/usr/bin/env python3
"""
Termux AI Bot (Improved)
-------------
A menu-driven AI assistant for Termux.
"""

import os
import sys
import json
import re
import subprocess
from datetime import datetime
import requests

CONFIG_DIR = os.path.expanduser("~/.termux_ai_bot")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
HISTORY_PATH = os.path.join(CONFIG_DIR, "history.json")
SCRIPT_PATH = os.path.expanduser("~/aibot_last_script.sh")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022" # Updated to latest standard sonnet model format
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "openrouter/free"

# BASE System prompt (context will be injected at runtime)
BASE_SHELL_SYSTEM_PROMPT = """You write short bash scripts that run inside Termux on Android.
Rules:
- Output ONLY a single bash code block. No explanation before or after.
- The script must be self-contained and runnable on Termux (assume `pkg` package manager, not `apt`).
- If a package is needed, include a `pkg install -y <package>` line at the top, but skip re-installing if already present.
- Never include destructive commands (no rm -rf /, no formatting storage, no modifying system files).
- Keep it as simple as possible while doing the job well.
"""

CHAT_SYSTEM_PROMPT = "You are a helpful, concise AI assistant chatting with a user inside a Termux terminal on Android."

session_log = []

def log(event: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    session_log.append(f"[{stamp}] {event}")

# ---------- Context & Safety ----------

def get_system_context() -> str:
    """Grabs basic Termux context to help the AI write better scripts."""
    try:
        uname = subprocess.check_output(["uname", "-a"], text=True, stderr=subprocess.DEVNULL).strip()
        pwd = subprocess.check_output(["pwd"], text=True, stderr=subprocess.DEVNULL).strip()
        return f"\n\nCURRENT SYSTEM CONTEXT:\n- OS/Kernel: {uname}\n- Current Directory: {pwd}"
    except Exception:
        return ""

def is_safe_script(script: str) -> list:
    """Scans the script for potentially dangerous commands."""
    dangers = []
    # Regex patterns for dangerous commands
    patterns = {
        r"rm\s+-r": "Recursive remove (rm -r)",
        r"mkfs": "Filesystem creation (mkfs)",
        r"dd\s+if=": "Low-level copy (dd)",
        r">\s*/dev/": "Writing directly to device files",
        r"chmod\s+-R\s+777": "Recursive full permissions (chmod -R 777)"
    }
    for pattern, warning in patterns.items():
        if re.search(pattern, script):
            dangers.append(warning)
    return dangers

# ---------- Config (API key management) ----------

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def save_config(cfg: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)

def setup_api_key(cfg: dict) -> dict:
    print("\n=== API Key Setup ===")
    print("1) Anthropic (Claude)")
    print("2) OpenRouter (many free models)")
    choice = input("Choose provider [1/2]: ").strip()
    if choice == "1":
        key = input("Enter your Anthropic API key (sk-ant-...): ").strip()
        cfg["provider"] = "anthropic"
        cfg["anthropic_api_key"] = key
    else:
        key = input("Enter your OpenRouter API key (sk-or-v1-...): ").strip()
        model = input(f"Model to use [default: {DEFAULT_OPENROUTER_MODEL}]: ").strip()
        cfg["provider"] = "openrouter"
        cfg["openrouter_api_key"] = key
        cfg["openrouter_model"] = model if model else DEFAULT_OPENROUTER_MODEL
    save_config(cfg)
    print("Saved.\n")
    log(f"API key configured for provider={cfg['provider']}")
    return cfg

def manage_api_keys(cfg: dict) -> dict:
    while True:
        print("\n=== API Keys ===")
        provider = cfg.get("provider", "not set")
        print(f"Current provider: {provider}")
        if provider == "anthropic":
            key = cfg.get("anthropic_api_key", "")
            print(f"Anthropic key: {mask_key(key)}")
        elif provider == "openrouter":
            key = cfg.get("openrouter_api_key", "")
            print(f"OpenRouter key: {mask_key(key)}")
            print(f"Model: {cfg.get('openrouter_model', DEFAULT_OPENROUTER_MODEL)}")
        print("\n1) Change / set API key")
        print("2) Clear saved key")
        print("3) Back to main menu")
        choice = input("> ").strip()
        if choice == "1":
            cfg = setup_api_key(cfg)
        elif choice == "2":
            cfg.pop("provider", None)
            cfg.pop("anthropic_api_key", None)
            cfg.pop("openrouter_api_key", None)
            cfg.pop("openrouter_model", None)
            save_config(cfg)
            print("Cleared.")
            log("API key cleared")
        elif choice == "3":
            return cfg
        else:
            print("Invalid choice.")

def mask_key(key: str) -> str:
    if not key:
        return "(none)"
    if len(key) <= 8:
        return "****"
    return f"{key[:8]}...{key[-4:]}"

def ensure_config(cfg: dict) -> dict:
    if not cfg.get("provider"):
        print("No API key configured yet.")
        cfg = setup_api_key(cfg)
    return cfg

# ---------- AI calls ----------

def call_ai(cfg: dict, system_prompt: str, user_message: str) -> str:
    provider = cfg.get("provider")
    if provider == "anthropic":
        return call_anthropic(cfg, system_prompt, user_message)
    elif provider == "openrouter":
        return call_openrouter(cfg, system_prompt, user_message)
    else:
        print("ERROR: no provider configured.")
        sys.exit(1)

def call_anthropic(cfg: dict, system_prompt: str, user_message: str) -> str:
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    headers = {
        "x-api-key": cfg.get("anthropic_api_key", ""),
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
        return f"[ERROR] API request failed: {e}"

def call_openrouter(cfg: dict, system_prompt: str, user_message: str) -> str:
    model = cfg.get("openrouter_model", DEFAULT_OPENROUTER_MODEL)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    headers = {
        "Authorization": f"Bearer {cfg.get('openrouter_api_key', '')}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(OPENROUTER_API_URL, headers=headers, data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return f"[ERROR] Unexpected response: {data}"
        return choices[0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        return f"[ERROR] API request failed: {e}"

def extract_script(ai_text: str) -> str:
    match = re.search(r"```(?:bash|sh)?\n(.*?)```", ai_text, re.DOTALL)
    if not match:
        match = re.search(r"```\n(.*?)```", ai_text, re.DOTALL)
    return match.group(1).strip() if match else ai_text.strip()

# ---------- History ----------

def load_history() -> list:
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r") as f:
            return json.load(f)
    return []

def save_history(history: list) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # Keep last 100 entries only
    with open(HISTORY_PATH, "w") as f:
        json.dump(history[-100:], f, indent=2)

def add_to_history(mode: str, request: str, reply: str) -> None:
    history = load_history()
    history.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "request": request,
        "reply": reply,
    })
    save_history(history)

def view_history() -> None:
    history = load_history()
    if not history:
        print("\nNo history yet.")
        return
    print(f"\n=== History (last {len(history)}) ===")
    for i, entry in enumerate(history, 1):
        print(f"\n{i}. [{entry['time']}] ({entry['mode']})")
        print(f"   You: {entry['request'][:80]}")
        print(f"   AI:  {entry['reply'][:120]}")

# ---------- Modes ----------

def chat_mode(cfg: dict) -> None:
    print("\n=== Chat Mode === (type 'exit' to return to menu)\n")
    while True:
        user_message = input("You: ").strip()
        if user_message.lower() in ("exit", "quit", "back"):
            break
        if not user_message:
            continue
        log(f"Chat request: {user_message[:50]}")
        reply = call_ai(cfg, CHAT_SYSTEM_PROMPT, user_message)
        print(f"\nAI: {reply}\n")
        add_to_history("chat", user_message, reply)
        log("Chat reply received")

def code_mode(cfg: dict) -> None:
    print("\n=== Code Mode ===")
    request = input("What do you want your Termux bot to do?\n> ").strip()
    if not request:
        print("No request given.")
        return
    log(f"Code request: {request[:50]}")
    
    # Inject context into system prompt
    current_system_prompt = BASE_SHELL_SYSTEM_PROMPT + get_system_context()
    
    current_request = request
    while True:
        print("\n[Asking AI to write the script...]\n")
        ai_reply = call_ai(cfg, current_system_prompt, current_request)
        script = extract_script(ai_reply)
        
        print("----- Generated script -----")
        print(script)
        print("-----------------------------\n")
        add_to_history("code", current_request, script)
        log("Code reply received")
        
        with open(SCRIPT_PATH, "w") as f:
            f.write(script)
        os.chmod(SCRIPT_PATH, 0o755)
        
        # Safety Check
        dangers = is_safe_script(script)
        if dangers:
            print("!!! WARNING: POTENTIALLY DANGEROUS COMMANDS DETECTED !!!")
            for d in dangers:
                print(f" - {d}")
            print("Please review the script carefully before running.\n")
        
        run_choice = input("Run this script now? [y/N]: ").strip().lower()
        if run_choice == "y":
            print("\n[Running...]\n")
            log("Ran generated script")
            
            # Capture output for Self-Healing
            result = subprocess.run(["bash", SCRIPT_PATH], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(result.stdout)
                print("\n[Success! Script finished without errors.]")
                break # Exit the loop on success
            else:
                print(result.stdout)
                print(f"\n[ERROR] Script exited with code {result.returncode}:\n{result.stderr.strip()}")
                
                # Self-Healing loop
                fix_choice = input("\nAsk AI to fix this error? [y/N]: ").strip().lower()
                if fix_choice == "y":
                    current_request = f"My original request was: '{request}'.\nThe script you gave me failed with this error:\n{result.stderr}\nPlease provide a corrected bash script."
                    log("Initiated self-healing sequence")
                    continue # Loop back up and ask AI again
                else:
                    break # User declined fix, exit loop
        else:
            print(f"Not run. Saved at {SCRIPT_PATH} — you can review/run it manually with:")
            print(f"  bash {SCRIPT_PATH}")
            log("Did not run generated script")
            break

def show_help() -> None:
    print("""
=== Help ===
1) Chat Mode    - Have an open conversation with the AI.
2) Code Mode    - Describe a task in plain English; the AI writes a
                  Termux-compatible bash script. You review it, then
                  choose whether to run it. If it fails, you can auto-fix it.
3) API Keys     - Set, view (masked), change, or clear your API key
                  and provider (Anthropic or OpenRouter).
4) History      - See your past requests and AI replies.
5) Session Log  - See a timestamped log of everything done this run.
6) Help         - This screen.
7) Credits      - About this tool.
8) Exit         - Quit.
""")

def show_credits() -> None:
    print("""
=== Credits ===
Termux AI Bot
A personal AI assistant for Termux, built with Python + requests.
Supports Anthropic (Claude) and OpenRouter as providers.
""")

def main_menu() -> str:
    print("\n=== Termux AI Bot ===")
    print("1) Chat Mode")
    print("2) Code Mode")
    print("3) API Keys")
    print("4) History")
    print("5) Session Log")
    print("6) Help")
    print("7) Credits")
    print("8) Exit")
    return input("> ").strip()

def main():
    cfg = load_config()
    cfg = ensure_config(cfg)
    while True:
        choice = main_menu()
        if choice == "1":
            cfg = ensure_config(cfg)
            chat_mode(cfg)
        elif choice == "2":
            cfg = ensure_config(cfg)
            code_mode(cfg)
        elif choice == "3":
            cfg = manage_api_keys(cfg)
        elif choice == "4":
            view_history()
        elif choice == "5":
            print("\n=== Session Log ===")
            if not session_log:
                print("Nothing logged yet this session.")
            for line in session_log:
                print(line)
        elif choice == "6":
            show_help()
        elif choice == "7":
            show_credits()
        elif choice == "8":
            print("Bye!")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
