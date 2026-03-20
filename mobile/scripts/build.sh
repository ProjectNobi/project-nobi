#!/bin/bash
# ============================================================
# Nori - AI Companion | Build Script
# Usage: bash scripts/build.sh [ios|android|all] [profile]
# Profiles: development | preview | production (default: production)
# ============================================================

set -euo pipefail

PLATFORM="${1:-all}"
PROFILE="${2:-production}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ---- Prerequisites ----
info "Checking prerequisites..."

command -v node  >/dev/null 2>&1 || error "Node.js is not installed."
command -v npx   >/dev/null 2>&1 || error "npx is not available."
command -v eas   >/dev/null 2>&1 || error "EAS CLI is not installed. Run: npm install -g eas-cli"

# ---- EAS Auth ----
info "Checking EAS login status..."
if ! eas whoami >/dev/null 2>&1; then
  error "Not logged in to EAS. Run: eas login"
fi
EAS_USER=$(eas whoami 2>/dev/null)
info "Logged in as: $EAS_USER"

# ---- Validate config ----
if [ ! -f "app.json" ]; then
  error "app.json not found. Run this script from the mobile/ directory."
fi
if [ ! -f "eas.json" ]; then
  error "eas.json not found."
fi

info "Building platform=$PLATFORM profile=$PROFILE"

# ---- Build functions ----
build_ios() {
  info "Starting iOS build (profile: $PROFILE)..."
  eas build --platform ios --profile "$PROFILE" --non-interactive
  info "iOS build submitted successfully."
}

build_android() {
  info "Starting Android build (profile: $PROFILE)..."
  eas build --platform android --profile "$PROFILE" --non-interactive
  info "Android build submitted successfully."
}

# ---- Dispatch ----
case "$PLATFORM" in
  ios)
    build_ios
    ;;
  android)
    build_android
    ;;
  all)
    build_ios
    build_android
    ;;
  *)
    error "Unknown platform: $PLATFORM. Use: ios | android | all"
    ;;
esac

info "============================================"
info "Build complete! Check status with: eas build:list"
info "Submit to stores with: eas submit --platform [ios|android] --profile production"
info "============================================"
