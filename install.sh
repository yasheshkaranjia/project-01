#!/data/data/com.termux/files/usr/bin/bash
set -e

REPO_URL="https://github.com/yasheshkaranjia/project-01.git"
REPO_DIR="$HOME/project-01"

echo "=================================="
echo " Termux AI Bot — Installer"
echo "=================================="

echo "Setting up storage access..."
termux-setup-storage

echo "Updating packages..."
yes | pkg update
yes | pkg upgrade

echo "Installing dependencies..."
yes | pkg install git python gum jq -y

echo "Installing pip dependencies..."
pip install requests

if [ -d "$REPO_DIR/.git" ]; then
    echo "Repo already exists, pulling latest..."
    cd "$REPO_DIR"
    git pull
else
    echo "Cloning repo..."
    git clone "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi

echo ""
echo "=================================="
echo "Installation complete!"
echo "Launching Termux AI Bot..."
echo "=================================="
echo ""

# ======================================================
# Termux AI Bot — main app (runs immediately after setup)
# ======================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

CONFIG_DIR="$HOME/.config/termux-ai-bot"
CONFIG_FILE="$CONFIG_DIR/config"
HISTORY_FILE="$CONFIG_DIR/history"
SESSION_FILE="$CONFIG_DIR/session_$(date +%Y%m%d_%H%M%S).txt"
SCRIPT_PATH="$HOME/aibot_last_script.sh"

ANTHROPIC_API_URL="https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL="claude-sonnet-4-6"
OPENROUTER_API_URL="https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL="openrouter/free"

SHELL_SYSTEM_PROMPT='You write short bash scripts that run inside Termux on Android. Rules: Output ONLY a single bash code block, no explanation before or after. The script must be self-contained and runnable on Termux (use pkg, not apt). Include pkg install -y lines for anything needed, but skip re-installing if already present (use command -v checks). Never include destructive commands. Keep it simple.'
CHAT_SYSTEM_PROMPT='You are a helpful, concise AI assistant chatting with a user inside a Termux terminal on Android.'

init_config() {
    mkdir -p "$CONFIG_DIR"
    [ -f "$CONFIG_FILE" ] || cat > "$CONFIG_FILE" << EOF
PROVIDER=""
OPENROUTER_KEY=""
OPENROUTER_MODEL="$DEFAULT_OPENROUTER_MODEL"
ANTHROPIC_KEY=""
EOF
    touch "$HISTORY_FILE" "$SESSION_FILE"
    chmod 600 "$CONFIG_FILE"
}

load_config() { source "$CONFIG_FILE"; }

save_config() {
    cat > "$CONFIG_FILE" << EOF
PROVIDER="$PROVIDER"
OPENROUTER_KEY="$OPENROUTER_KEY"
OPENROUTER_MODEL="$OPENROUTER_MODEL"
ANTHROPIC_KEY="$ANTHROPIC_KEY"
EOF
    chmod 600 "$CONFIG_FILE"
}

mask_key() {
    local key="$1"
    [ -z "$key" ] && echo "(none)" && return
    echo "${key:0:8}...${key: -4}"
}

log_session() { echo "[$(date '+%H:%M:%S')] $1" >> "$SESSION_FILE"; }

log_history() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] MODE=$1" >> "$HISTORY_FILE"
    echo "You: $2" >> "$HISTORY_FILE"
    echo "AI:  $3" >> "$HISTORY_FILE"
    echo "---" >> "$HISTORY_FILE"
}

show_banner() {
    clear
    gum style \
        --foreground 212 --border double --border-foreground 212 \
        --padding "1 2" --margin "1 2" \
        "TERMUX AI BOT" \
        "Your personal AI assistant"
}

setup_api_key() {
    show_banner
    echo -e "${CYAN}API Key Setup${NC}\n"
    PROVIDER=$(gum choose --height=4 --cursor="> " "anthropic" "openrouter")

    if [ "$PROVIDER" = "anthropic" ]; then
        ANTHROPIC_KEY=$(gum input --placeholder "Paste your Anthropic key (sk-ant-...)" --password)
    else
        OPENROUTER_KEY=$(gum input --placeholder "Paste your OpenRouter key (sk-or-v1-...)" --password)
        MODEL_INPUT=$(gum input --placeholder "Model [default: $DEFAULT_OPENROUTER_MODEL]")
        OPENROUTER_MODEL="${MODEL_INPUT:-$DEFAULT_OPENROUTER_MODEL}"
    fi

    save_config
    log_session "API key configured for provider=$PROVIDER"
    gum style --foreground 82 "Saved!"
    sleep 1
}

ensure_config() {
    if [ -z "$PROVIDER" ]; then
        gum style --foreground 214 "No API key configured yet."
        setup_api_key
    fi
}

call_ai() {
    local system_prompt="$1"
    local user_message="$2"

    if [ "$PROVIDER" = "anthropic" ]; then
        call_anthropic "$system_prompt" "$user_message"
    else
        call_openrouter "$system_prompt" "$user_message"
    fi
}

call_anthropic() {
    local system_prompt="$1"
    local user_message="$2"
    local payload
    payload=$(jq -n --arg sys "$system_prompt" --arg msg "$user_message" --arg model "$ANTHROPIC_MODEL" \
        '{model: $model, max_tokens: 1024, system: $sys, messages: [{role: "user", content: $msg}]}')

    curl -s -X POST "$ANTHROPIC_API_URL" \
        -H "x-api-key: $ANTHROPIC_KEY" \
        -H "anthropic-version: 2023-06-01" \
        -H "content-type: application/json" \
        -d "$payload" | jq -r '[.content[]? | select(.type=="text") | .text] | join("\n")'
}

call_openrouter() {
    local system_prompt="$1"
    local user_message="$2"
    local payload
    payload=$(jq -n --arg sys "$system_prompt" --arg msg "$user_message" --arg model "$OPENROUTER_MODEL" \
        '{model: $model, messages: [{role: "system", content: $sys}, {role: "user", content: $msg}]}')

    curl -s -X POST "$OPENROUTER_API_URL" \
        -H "Authorization: Bearer $OPENROUTER_KEY" \
        -H "Content-Type: application/json" \
        -d "$payload" | jq -r '.choices[0].message.content // ("[ERROR] " + (.error.message // "unknown error"))'
}

extract_script() {
    local text="$1"
    echo "$text" | sed -n '/```/,/```/p' | sed '1d;$d'
}

chat_mode() {
    ensure_config
    show_banner
    echo -e "${CYAN}Chat Mode${NC} | Provider: $PROVIDER"
    echo -e "${YELLOW}Type 'exit' to return to menu${NC}\n"

    while true; do
        QUESTION=$(gum input --placeholder "Ask me anything..." --prompt "> " --width 80)
        [ "$QUESTION" = "exit" ] && return
        [ -z "$QUESTION" ] && continue

        log_session "Chat request: $QUESTION"
        RESPONSE=$(call_ai "$CHAT_SYSTEM_PROMPT" "$QUESTION")
        echo -e "\n${GREEN}AI:${NC} $RESPONSE\n"
        log_history "chat" "$QUESTION" "$RESPONSE"
        log_session "Chat reply received"
    done
}

code_mode() {
    ensure_config
    show_banner
    echo -e "${CYAN}Code Mode${NC} | Provider: $PROVIDER\n"

    REQUEST=$(gum input --placeholder "What do you want your Termux bot to do?" --width 80)
    [ -z "$REQUEST" ] && return

    log_session "Code request: $REQUEST"
    echo -e "\n${YELLOW}Asking AI to write the script...${NC}\n"
    AI_REPLY=$(call_ai "$SHELL_SYSTEM_PROMPT" "$REQUEST")
    SCRIPT=$(extract_script "$AI_REPLY")
    [ -z "$SCRIPT" ] && SCRIPT="$AI_REPLY"

    echo -e "${CYAN}----- Generated script -----${NC}"
    echo "$SCRIPT"
    echo -e "${CYAN}-----------------------------${NC}\n"

    echo "$SCRIPT" > "$SCRIPT_PATH"
    chmod +x "$SCRIPT_PATH"
    log_history "code" "$REQUEST" "$SCRIPT"

    if gum confirm "Run this script now?"; then
        log_session "Ran generated script"
        bash "$SCRIPT_PATH"
    else
        echo -e "${YELLOW}Not run. Saved at $SCRIPT_PATH${NC}"
        log_session "Did not run generated script"
    fi
}

api_keys_menu() {
    while true; do
        show_banner
        echo -e "${CYAN}API Keys${NC}\n"
        echo "Provider: ${PROVIDER:-not set}"
        [ "$PROVIDER" = "anthropic" ] && echo "Key: $(mask_key "$ANTHROPIC_KEY")"
        [ "$PROVIDER" = "openrouter" ] && echo "Key: $(mask_key "$OPENROUTER_KEY")" && echo "Model: $OPENROUTER_MODEL"
        echo

        ACTION=$(gum choose --height=4 --cursor="> " "Change / set API key" "Clear saved key" "Back to Main Menu")
        case "$ACTION" in
            "Change / set API key") setup_api_key ;;
            "Clear saved key")
                PROVIDER=""; ANTHROPIC_KEY=""; OPENROUTER_KEY=""; OPENROUTER_MODEL="$DEFAULT_OPENROUTER_MODEL"
                save_config
                log_session "API key cleared"
                gum style --foreground 214 "Cleared."
                sleep 1
                ;;
            "Back to Main Menu") return ;;
        esac
    done
}

view_history() {
    show_banner
    echo -e "${CYAN}History${NC}\n"
    if [ -s "$HISTORY_FILE" ]; then
        tail -60 "$HISTORY_FILE"
    else
        echo -e "${YELLOW}No history yet.${NC}"
    fi
    echo
    gum input --placeholder "Press Enter to continue..."
}

view_session_log() {
    show_banner
    echo -e "${CYAN}Session Log${NC}\n"
    if [ -s "$SESSION_FILE" ]; then cat "$SESSION_FILE"; else echo -e "${YELLOW}Nothing logged yet.${NC}"; fi
    echo
    gum input --placeholder "Press Enter to continue..."
}

show_help() {
    show_banner
    echo -e "${CYAN}Help${NC}\n"
    cat << 'EOF'
Chat Mode    - Open conversation with the AI.
Code Mode    - Describe a task; AI writes a bash script; you choose to run it.
API Keys     - Set / view (masked) / clear your provider and key.
History      - Past requests & replies (~/.config/termux-ai-bot/history).
Session Log  - What happened this run.
Credits      - About this tool.
Exit         - Quit.
EOF
    echo
    gum input --placeholder "Press Enter to continue..."
}

show_credits() {
    show_banner
    echo -e "${CYAN}Credits${NC}\n"
    echo "Termux AI Bot — personal project by yasheshkaranjia"
    echo "Interface style inspired by Anon4You/Termux-Ai (gum + tgpt)."
    echo "This version calls Anthropic/OpenRouter directly via curl."
    echo
    gum input --placeholder "Press Enter to continue..."
}

show_main_menu() {
    while true; do
        show_banner
        echo -e "${CYAN}Main Menu${NC}\n"
        CHOICE=$(gum choose --height=10 --cursor="> " \
            "Chat Mode" "Code Mode" "API Keys" "History" "Session Log" "Help" "Credits" "Exit")

        case "$CHOICE" in
            "Chat Mode") chat_mode ;;
            "Code Mode") code_mode ;;
            "API Keys") api_keys_menu ;;
            "History") view_history ;;
            "Session Log") view_session_log ;;
            "Help") show_help ;;
            "Credits") show_credits ;;
            "Exit") echo -e "${GREEN}Bye!${NC}"; exit 0 ;;
        esac
    done
}

init_config
load_config
ensure_config
show_main_menu
