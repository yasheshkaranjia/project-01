# project-01 — Termux AI Bot

A personal AI assistant for [Termux](https://termux.dev/) on Android.
You describe a task in plain English, an AI (Claude) writes a Termux-compatible
bash script for it, and — after you review and approve it — the script runs
right there in your terminal.

**Example:**
```
python aibot.py "play an online radio station"
```
The bot asks Claude for a script, shows it to you, and only runs it if you
type `y`.

---

## Setup

### 1. Install Termux prerequisites
```bash
pkg update && pkg upgrade
pkg install python
pip install requests
```

### 2. Get an Anthropic API key
Create one at [console.anthropic.com](https://console.anthropic.com) (this is
the pay-as-you-go API, separate from a claude.ai subscription).

### 3. Set your API key as an environment variable
```bash
export ANTHROPIC_API_KEY="sk-ant-your-real-key-here"
```
To make this permanent, add that line to your `~/.bashrc` (or `~/.zshrc`).

### 4. Run it
```bash
python aibot.py "your request here"
```
or run with no arguments for interactive mode:
```bash
python aibot.py
```

---

## How it works

1. You type a request.
2. The script sends it to Claude's API with instructions to reply with
   **only** a runnable bash script suited to Termux.
3. The generated script is extracted, saved to `~/aibot_last_script.sh`,
   and printed to your terminal.
4. You're asked to confirm before anything executes — nothing runs
   automatically.
5. If you approve, the script runs.

## Troubleshooting

- **API errors**: Verify your API key is set correctly and has sufficient credits
- **Script not running**: Check file permissions on the generated script (`chmod +x aibot_last_script.sh`)
- **Missing packages**: The script may require additional Termux packages - check the generated script for `pkg install` commands

## Safety notes

- **Always read the generated script before approving it.** AI-generated
  shell code can occasionally be wrong or do more than you expect.
- The bot is instructed never to generate destructive commands (no
  `rm -rf /`, no storage wipes, no system file edits), but you're the
  last line of defense — review before running.
- Never commit your `ANTHROPIC_API_KEY` to this repo. Keep it as an
  environment variable only (see `.gitignore`).

## Files

- `aibot.py` — the main script
- `README.md` — this file

## Roadmap / ideas

- Support for additional AI providers (e.g. Kimi)
- A "favorites" menu for common tasks (radio, weather, timers) to skip
  re-typing requests
- Persistent memory of past generated scripts
