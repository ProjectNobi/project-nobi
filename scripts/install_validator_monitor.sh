#!/usr/bin/env bash
# install_validator_monitor.sh — One-command installer for the Validator Monitor.
#
# Usage:
#   bash scripts/install_validator_monitor.sh
#
# This script:
#   1. Auto-detects validator PM2 processes
#   2. Installs the validator monitor as a PM2 cron (every 15 minutes)
#   3. Logs health to ~/.nobi/validator_health.json
#   4. Saves PM2 process list

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
MONITOR_SCRIPT="$SCRIPT_DIR/validator_monitor.py"
PM2_NAME="nobi-validator-monitor"
HEALTH_DIR="$HOME/.nobi"
HEALTH_FILE="$HEALTH_DIR/validator_health.json"

echo "============================================"
echo "  Project Nobi — Validator Monitor Installer"
echo "============================================"
echo ""

# Check prerequisites
if ! command -v pm2 &>/dev/null; then
    echo "ERROR: pm2 is not installed. Install it with: npm install -g pm2"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed."
    exit 1
fi

if [ ! -f "$MONITOR_SCRIPT" ]; then
    echo "ERROR: Monitor script not found at $MONITOR_SCRIPT"
    exit 1
fi

# Create health directory
mkdir -p "$HEALTH_DIR"

# Auto-detect validator processes
echo "🔍 Detecting validator PM2 processes..."
VALIDATORS=$(python3 -c "
import subprocess, json, sys
try:
    r = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        sys.exit(0)
    procs = json.loads(r.stdout)
    names = [p['name'] for p in procs if isinstance(p, dict) and ('validator' in p.get('name','').lower() or 'nobi-v' in p.get('name','').lower())]
    print(' '.join(names))
except:
    pass
" 2>/dev/null || true)

if [ -n "$VALIDATORS" ]; then
    echo "  Found validators: $VALIDATORS"
else
    echo "  No validator processes detected (will auto-detect at runtime)"
fi

# Stop existing monitor if running
if pm2 describe "$PM2_NAME" &>/dev/null; then
    echo "🔄 Stopping existing monitor..."
    pm2 delete "$PM2_NAME" 2>/dev/null || true
fi

# Install as PM2 cron process (every 15 minutes)
echo "📦 Installing validator monitor as PM2 cron..."
pm2 start "$MONITOR_SCRIPT" \
    --name "$PM2_NAME" \
    --interpreter python3 \
    --cron-restart "*/15 * * * *" \
    --no-autorestart \
    -- --save --health-file "$HEALTH_FILE"

# Save PM2 process list
pm2 save

echo ""
echo "✅ Validator Monitor installed!"
echo ""
echo "  PM2 process:  $PM2_NAME"
echo "  Health file:   $HEALTH_FILE"
echo "  Schedule:      Every 15 minutes"
echo ""
echo "Commands:"
echo "  pm2 logs $PM2_NAME        # View monitor logs"
echo "  cat $HEALTH_FILE           # View latest health"
echo "  python3 $MONITOR_SCRIPT    # Run manually (full report)"
echo "  pm2 delete $PM2_NAME       # Uninstall"
echo ""
