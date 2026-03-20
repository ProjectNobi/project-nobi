#!/bin/bash
# ===================================================================
# Project Nobi — One-Command Miner Setup
# ===================================================================
# Usage: curl -sSL https://raw.githubusercontent.com/ProjectNobi/project-nobi/main/scripts/quick_setup.sh | bash
# Or:    bash <(curl -sSL https://raw.githubusercontent.com/ProjectNobi/project-nobi/main/scripts/quick_setup.sh)
#
# What this does:
#   1. Installs dependencies (Python, pip, git, pm2)
#   2. Clones the repo
#   3. Creates a virtual environment
#   4. Installs Project Nobi
#   5. Walks you through wallet creation & registration
#   6. Starts the miner with PM2
#
# Requirements: Ubuntu/Debian 20.04+, 2+ cores, 2GB+ RAM, no GPU needed
# ===================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Banner
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════╗"
echo "║        🤖 Project Nobi — Miner Setup        ║"
echo "║     Personal AI Companions for Everyone      ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Helper functions ──────────────────────────────────────────

log_info()  { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_step()  { echo -e "\n${BLUE}${BOLD}── $1 ──${NC}"; }
ask()       { echo -en "${CYAN}[?]${NC} $1: "; }

# ── Preflight checks ─────────────────────────────────────────

log_step "Preflight Checks"

# Check OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    log_info "OS: $PRETTY_NAME"
else
    log_warn "Could not detect OS. This script targets Ubuntu/Debian."
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    log_warn "Running as root. Consider using a non-root user for production."
fi

# Check minimum resources
CORES=$(nproc 2>/dev/null || echo "?")
RAM_MB=$(free -m 2>/dev/null | awk '/Mem:/{print $2}' || echo "?")
DISK_GB=$(df -BG / 2>/dev/null | awk 'NR==2{print $4}' | tr -d 'G' || echo "?")
log_info "Resources: ${CORES} cores, ${RAM_MB}MB RAM, ${DISK_GB}GB free disk"

if [ "$RAM_MB" != "?" ] && [ "$RAM_MB" -lt 1500 ]; then
    log_error "Minimum 2GB RAM required. You have ${RAM_MB}MB."
    exit 1
fi

# ── Install system dependencies ───────────────────────────────

log_step "Installing System Dependencies"

# Update package lists
sudo apt-get update -qq

# Python
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    log_info "Python: $PY_VER"
else
    log_info "Installing Python 3..."
    sudo apt-get install -y python3 python3-venv python3-pip
fi

# pip
if ! python3 -m pip --version &>/dev/null; then
    log_info "Installing pip..."
    sudo apt-get install -y python3-pip
fi

# git
if ! command -v git &>/dev/null; then
    log_info "Installing git..."
    sudo apt-get install -y git
fi

# Node.js + PM2
if ! command -v pm2 &>/dev/null; then
    if ! command -v node &>/dev/null; then
        log_info "Installing Node.js..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
    log_info "Installing PM2..."
    sudo npm install -g pm2
fi

log_info "All system dependencies installed"

# ── Clone & Install Project Nobi ──────────────────────────────

log_step "Installing Project Nobi"

INSTALL_DIR="${HOME}/project-nobi"

if [ -d "$INSTALL_DIR" ]; then
    log_info "Project Nobi already exists at $INSTALL_DIR"
    cd "$INSTALL_DIR"
    git pull origin main 2>/dev/null || log_warn "Could not pull latest (offline?)"
else
    log_info "Cloning Project Nobi..."
    git clone https://github.com/ProjectNobi/project-nobi.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Virtual environment
if [ ! -d "venv" ]; then
    log_info "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
log_info "Virtual environment activated"

# Install
log_info "Installing dependencies (this may take 1-2 minutes)..."
pip install --quiet --upgrade pip
pip install --quiet -e .
pip install --quiet bittensor-cli

# Optional: install sentence-transformers for semantic memory
pip install --quiet sentence-transformers scikit-learn 2>/dev/null || \
    log_warn "Sentence-transformers not installed (optional — falls back to keyword matching)"

# Verify
python3 -c "import nobi; print('nobi OK')" 2>/dev/null && log_info "Project Nobi installed" || log_error "Installation failed"
python3 -c "import bittensor as bt; print(f'bittensor {bt.__version__}')" 2>/dev/null && log_info "Bittensor installed" || log_error "Bittensor installation failed"

# ── Wallet Setup ──────────────────────────────────────────────

log_step "Wallet Setup"

WALLET_NAME=""
HOTKEY_NAME=""

echo -e "${CYAN}Do you already have a Bittensor wallet? (y/n)${NC}"
read -r HAS_WALLET

if [ "$HAS_WALLET" = "y" ] || [ "$HAS_WALLET" = "Y" ]; then
    ask "Wallet (coldkey) name"
    read -r WALLET_NAME
    ask "Hotkey name"
    read -r HOTKEY_NAME
else
    ask "Choose a wallet name (e.g., my_wallet)"
    read -r WALLET_NAME
    WALLET_NAME=${WALLET_NAME:-my_wallet}

    ask "Choose a hotkey name (e.g., nobi-miner)"
    read -r HOTKEY_NAME
    HOTKEY_NAME=${HOTKEY_NAME:-nobi-miner}

    log_info "Creating wallet '$WALLET_NAME' with hotkey '$HOTKEY_NAME'..."
    echo -e "${YELLOW}IMPORTANT: Save the mnemonic phrases shown below! They are your backup.${NC}"
    echo ""
    btcli wallet new-coldkey --wallet.name "$WALLET_NAME" 2>/dev/null || \
        python3 -m bittensor_cli.cli wallet new-coldkey --wallet.name "$WALLET_NAME"
    btcli wallet new-hotkey --wallet.name "$WALLET_NAME" --wallet.hotkey "$HOTKEY_NAME" 2>/dev/null || \
        python3 -m bittensor_cli.cli wallet new-hotkey --wallet.name "$WALLET_NAME" --wallet.hotkey "$HOTKEY_NAME"
fi

# ── Registration ──────────────────────────────────────────────

log_step "Subnet Registration (SN272 Testnet)"

echo -e "${CYAN}Register on testnet now? This costs a small amount of tTAO. (y/n)${NC}"
read -r DO_REGISTER

if [ "$DO_REGISTER" = "y" ] || [ "$DO_REGISTER" = "Y" ]; then
    log_info "Registering on SN272..."
    btcli subnets register \
        --netuid 272 \
        --wallet.name "$WALLET_NAME" \
        --wallet.hotkey "$HOTKEY_NAME" \
        --subtensor.network test 2>/dev/null || \
    python3 -m bittensor_cli.cli subnets register \
        --netuid 272 \
        --wallet.name "$WALLET_NAME" \
        --wallet.hotkey "$HOTKEY_NAME" \
        --subtensor.network test
    log_info "Registration complete"
else
    log_warn "Skipping registration. Run this later:"
    echo "  btcli subnets register --netuid 272 --wallet.name $WALLET_NAME --wallet.hotkey $HOTKEY_NAME --subtensor.network test"
fi

# ── LLM API Key ──────────────────────────────────────────────

log_step "LLM Configuration"

echo -e "${CYAN}Which LLM provider? (1=Chutes.ai, 2=OpenRouter, 3=Self-hosted)${NC}"
read -r LLM_CHOICE

CHUTES_API_KEY=""
OPENROUTER_API_KEY=""
LLM_BASE_URL=""

case "$LLM_CHOICE" in
    1)
        ask "Chutes API key"
        read -r CHUTES_API_KEY
        ;;
    2)
        ask "OpenRouter API key"
        read -r OPENROUTER_API_KEY
        ;;
    3)
        ask "Self-hosted API URL (e.g., http://localhost:8000/v1)"
        read -r LLM_BASE_URL
        ;;
    *)
        log_warn "Invalid choice. You can set CHUTES_API_KEY or OPENROUTER_API_KEY later."
        ;;
esac

# ── Firewall ──────────────────────────────────────────────────

log_step "Firewall Configuration"

MINER_PORT=8091
log_info "Opening port $MINER_PORT for validator connections..."

if command -v ufw &>/dev/null; then
    sudo ufw allow "$MINER_PORT"/tcp 2>/dev/null && log_info "UFW: port $MINER_PORT opened" || log_warn "UFW rule may already exist"
else
    sudo iptables -A INPUT -p tcp --dport "$MINER_PORT" -j ACCEPT 2>/dev/null && log_info "iptables: port $MINER_PORT opened" || log_warn "Could not configure iptables"
fi

# ── Detect public IP ──────────────────────────────────────────

PUBLIC_IP=$(curl -4 -s ifconfig.me 2>/dev/null || curl -4 -s icanhazip.com 2>/dev/null || echo "")
if [ -n "$PUBLIC_IP" ]; then
    log_info "Public IP: $PUBLIC_IP"
else
    log_warn "Could not detect public IP. You'll need to set --axon.external_ip manually."
    ask "Your server's public IP"
    read -r PUBLIC_IP
fi

# ── Create .env file ─────────────────────────────────────────

log_step "Creating Configuration"

ENV_FILE="$INSTALL_DIR/.env"
cat > "$ENV_FILE" <<EOF
# Project Nobi Miner Configuration
# Generated by quick_setup.sh on $(date -u +"%Y-%m-%d %H:%M UTC")

WALLET_NAME=${WALLET_NAME}
HOTKEY_NAME=${HOTKEY_NAME}
MINER_PORT=${MINER_PORT}
PUBLIC_IP=${PUBLIC_IP}

# LLM API Keys (set the one you're using)
CHUTES_API_KEY=${CHUTES_API_KEY}
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
LLM_BASE_URL=${LLM_BASE_URL}

# Optional: Wallet password (if coldkey is encrypted)
# WALLET_PASSWORD=your-password-here
EOF

log_info "Config saved to $ENV_FILE"

# ── Create start script ──────────────────────────────────────

START_SCRIPT="$INSTALL_DIR/start_miner.sh"
cat > "$START_SCRIPT" <<'STARTEOF'
#!/bin/bash
# Project Nobi — Start Miner
set -e
cd "$(dirname "$0")"
source venv/bin/activate
source .env 2>/dev/null

# Export API keys
[ -n "$CHUTES_API_KEY" ] && export CHUTES_API_KEY
[ -n "$OPENROUTER_API_KEY" ] && export OPENROUTER_API_KEY
[ -n "$WALLET_PASSWORD" ] && export WALLET_PASSWORD

exec python3 neurons/miner.py \
    --wallet.name "${WALLET_NAME:-my_wallet}" \
    --wallet.hotkey "${HOTKEY_NAME:-nobi-miner}" \
    --subtensor.network test \
    --netuid 272 \
    --axon.port "${MINER_PORT:-8091}" \
    --axon.external_ip "${PUBLIC_IP}" \
    --axon.external_port "${MINER_PORT:-8091}" \
    --blacklist.allow_non_registered \
    --logging.debug
STARTEOF
chmod +x "$START_SCRIPT"

# ── Start with PM2 ───────────────────────────────────────────

log_step "Starting Miner"

echo -e "${CYAN}Start miner with PM2 now? (y/n)${NC}"
read -r DO_START

if [ "$DO_START" = "y" ] || [ "$DO_START" = "Y" ]; then
    cd "$INSTALL_DIR"
    source .env 2>/dev/null

    pm2 delete nobi-miner 2>/dev/null || true

    CHUTES_API_KEY="$CHUTES_API_KEY" \
    OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
    WALLET_PASSWORD="${WALLET_PASSWORD:-}" \
    pm2 start "$START_SCRIPT" \
        --name nobi-miner \
        --interpreter bash \
        --max-restarts 10 \
        --restart-delay 5000

    pm2 save

    log_info "Miner started! Check status with: pm2 status"
    echo ""
    echo -e "${GREEN}${BOLD}✅ Setup Complete!${NC}"
    echo ""
    echo -e "  📊 Status:     ${CYAN}pm2 status${NC}"
    echo -e "  📋 Logs:       ${CYAN}pm2 logs nobi-miner${NC}"
    echo -e "  🔄 Restart:    ${CYAN}pm2 restart nobi-miner${NC}"
    echo -e "  ⏹  Stop:       ${CYAN}pm2 stop nobi-miner${NC}"
    echo -e "  ⚙️  Config:     ${CYAN}nano $ENV_FILE${NC}"
else
    echo ""
    echo -e "${GREEN}${BOLD}✅ Setup Complete!${NC}"
    echo ""
    echo -e "  To start:   ${CYAN}cd $INSTALL_DIR && bash start_miner.sh${NC}"
    echo -e "  Or with PM2: ${CYAN}pm2 start $START_SCRIPT --name nobi-miner --interpreter bash${NC}"
fi

echo ""
echo -e "  📖 Full Guide: ${CYAN}https://github.com/ProjectNobi/project-nobi/blob/main/docs/MINING_GUIDE.md${NC}"
echo -e "  💬 Discord:    ${CYAN}https://discord.gg/e6StezHM${NC}"
echo -e "  🤖 Try Nori:   ${CYAN}https://t.me/ProjectNobiBot${NC}"
echo ""
echo -e "${CYAN}Happy mining! Every query you serve makes someone's Nori smarter. 🤖${NC}"
