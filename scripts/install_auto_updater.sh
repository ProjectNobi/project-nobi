#!/usr/bin/env bash
# install_auto_updater.sh — One-command installer for the Project Nobi auto-updater.
#
# Usage:
#   bash scripts/install_auto_updater.sh
#
# This script:
#   1. Auto-detects nobi-related PM2 processes
#   2. Installs the auto-updater as a PM2-managed process
#   3. Saves the PM2 process list so it survives reboots

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
UPDATER_SCRIPT="$SCRIPT_DIR/auto_updater.py"
PM2_NAME="nobi-auto-updater"
CHECK_INTERVAL="${AUTO_UPDATE_INTERVAL:-300}"
BRANCH="${AUTO_UPDATE_BRANCH:-main}"

echo "============================================"
echo "  Project Nobi — Auto-Updater Installer"
echo "============================================"
echo ""

# Check prerequisites
if ! command -v pm2 &>/dev/null; then
    echo "ERROR: pm2 is not installed. Install it with: npm install -g pm2"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not found."
    exit 1
fi

if ! command -v git &>/dev/null; then
    echo "ERROR: git is not found."
    exit 1
fi

if [ ! -f "$UPDATER_SCRIPT" ]; then
    echo "ERROR: auto_updater.py not found at $UPDATER_SCRIPT"
    exit 1
fi

# Auto-detect nobi PM2 processes
echo "Detecting nobi-related PM2 processes..."
PM2_NAMES=$(pm2 jlist 2>/dev/null | python3 -c "
import json, sys
try:
    procs = json.load(sys.stdin)
    names = [p['name'] for p in procs if 'nobi' in p.get('name', '').lower() and p['name'] != '$PM2_NAME']
    print(','.join(names))
except:
    print('')
" 2>/dev/null || echo "")

if [ -z "$PM2_NAMES" ]; then
    echo "No nobi processes detected. The updater will still run but won't restart any processes."
    echo "You can set AUTO_UPDATE_PM2_NAMES later."
else
    echo "Detected PM2 processes: $PM2_NAMES"
fi

# Stop existing auto-updater if running
if pm2 describe "$PM2_NAME" &>/dev/null; then
    echo "Stopping existing auto-updater..."
    pm2 delete "$PM2_NAME" 2>/dev/null || true
fi

# Create log directory
mkdir -p ~/.nobi

# Start the auto-updater via PM2
echo ""
echo "Starting auto-updater (interval=${CHECK_INTERVAL}s, branch=${BRANCH})..."
pm2 start "$UPDATER_SCRIPT" \
    --name "$PM2_NAME" \
    --interpreter python3 \
    --no-autorestart \
    --restart-delay 10000 \
    --max-restarts 5 \
    -- \
    --repo "$REPO_DIR" \
    --interval "$CHECK_INTERVAL" \
    --branch "$BRANCH" \
    ${PM2_NAMES:+--pm2-names "$PM2_NAMES"}

# Save PM2 process list
pm2 save --force 2>/dev/null || true

echo ""
echo "============================================"
echo "  Auto-updater installed successfully!"
echo "============================================"
echo ""
echo "  PM2 process:  $PM2_NAME"
echo "  Repository:   $REPO_DIR"
echo "  Branch:       $BRANCH"
echo "  Interval:     ${CHECK_INTERVAL}s"
echo "  PM2 targets:  ${PM2_NAMES:-<none detected>}"
echo "  Logs:         ~/.nobi/update_log.json"
echo ""
echo "Commands:"
echo "  pm2 logs $PM2_NAME     — View auto-updater logs"
echo "  pm2 stop $PM2_NAME     — Pause auto-updates"
echo "  pm2 restart $PM2_NAME  — Resume auto-updates"
echo "  pm2 delete $PM2_NAME   — Remove auto-updater"
echo ""
echo "Manual one-time check:"
echo "  python3 scripts/auto_updater.py --once"
echo ""
