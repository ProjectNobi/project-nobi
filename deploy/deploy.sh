#!/usr/bin/env bash
# Project Nobi — One-Command Deployment Script
# Usage: bash deploy/deploy.sh [--env production|staging]
#
# Features:
#   - Pulls latest code (if git repo)
#   - Builds Docker images
#   - Runs health checks
#   - Automatic rollback on failure

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env"
ENVIRONMENT="production"
ROLLBACK=false
BACKUP_TAG=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${BLUE}[DEPLOY]${NC} $*"; }
ok()    { echo -e "${GREEN}[  OK  ]${NC} $*"; }
warn()  { echo -e "${YELLOW}[ WARN ]${NC} $*"; }
err()   { echo -e "${RED}[ERROR ]${NC} $*"; }

# ─── Parse Args ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        --help|-h)
            echo "Usage: bash deploy/deploy.sh [--env production|staging] [--rollback]"
            echo ""
            echo "Options:"
            echo "  --env ENV       Set environment (production|staging), default: production"
            echo "  --rollback      Rollback to previous deployment"
            echo "  -h, --help      Show this help"
            exit 0
            ;;
        *)
            err "Unknown option: $1"
            exit 1
            ;;
    esac
done

log "Deploying Project Nobi ($ENVIRONMENT)"
log "Project: $PROJECT_DIR"

# ─── Pre-flight Checks ──────────────────────────────────────
check_deps() {
    local missing=()
    for cmd in docker curl git; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    # Check docker compose (v2 plugin or standalone)
    if docker compose version &>/dev/null; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        missing+=("docker-compose")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        err "Missing required tools: ${missing[*]}"
        exit 1
    fi
    ok "Dependencies: docker, curl, git, compose"
}

check_env_file() {
    if [[ ! -f "$ENV_FILE" ]]; then
        warn ".env file not found at $ENV_FILE"
        if [[ -f "$SCRIPT_DIR/.env.example" ]]; then
            warn "Copying .env.example → .env (edit before production use!)"
            cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
        else
            err "No .env or .env.example found. Create $ENV_FILE first."
            exit 1
        fi
    fi
    ok "Environment file: $ENV_FILE"
}

# ─── Backup Current State ───────────────────────────────────
backup_current() {
    BACKUP_TAG="backup-$(date +%Y%m%d-%H%M%S)"
    log "Tagging current images as $BACKUP_TAG..."

    for svc in nobi-api nobi-webapp; do
        if docker image inspect "$svc:latest" &>/dev/null; then
            docker tag "$svc:latest" "$svc:$BACKUP_TAG" 2>/dev/null || true
        fi
    done
    ok "Backup tagged: $BACKUP_TAG"
}

# ─── Rollback ────────────────────────────────────────────────
rollback() {
    err "Deployment failed! Rolling back..."

    if [[ -n "$BACKUP_TAG" ]]; then
        for svc in nobi-api nobi-webapp; do
            if docker image inspect "$svc:$BACKUP_TAG" &>/dev/null; then
                docker tag "$svc:$BACKUP_TAG" "$svc:latest" 2>/dev/null || true
            fi
        done

        cd "$SCRIPT_DIR"
        $COMPOSE_CMD -f "$COMPOSE_FILE" up -d --no-build 2>/dev/null || true
        warn "Rolled back to $BACKUP_TAG"
    else
        warn "No backup tag available — manual intervention needed"
    fi
    exit 1
}

# ─── Pull Latest Code ───────────────────────────────────────
pull_code() {
    if [[ -d "$PROJECT_DIR/.git" ]]; then
        log "Pulling latest code..."
        cd "$PROJECT_DIR"
        git fetch origin
        git pull --ff-only origin main 2>/dev/null || \
            git pull --ff-only origin master 2>/dev/null || \
            warn "Could not fast-forward — using current code"
        ok "Code updated"
    else
        warn "Not a git repo — skipping pull"
    fi
}

# ─── Build & Deploy ─────────────────────────────────────────
build_and_deploy() {
    cd "$SCRIPT_DIR"

    log "Building Docker images..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache || rollback

    log "Starting services..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d || rollback

    ok "Services started"
}

# ─── Health Checks ───────────────────────────────────────────
health_check() {
    log "Running health checks..."
    local max_retries=15
    local retry_delay=4

    # Check API
    for i in $(seq 1 $max_retries); do
        if curl -sf http://localhost:8042/health &>/dev/null; then
            ok "API health check passed"
            break
        fi
        if [[ $i -eq $max_retries ]]; then
            err "API health check failed after $max_retries attempts"
            rollback
        fi
        sleep $retry_delay
    done

    # Check Webapp
    for i in $(seq 1 $max_retries); do
        if curl -sf http://localhost:3000 &>/dev/null; then
            ok "Webapp health check passed"
            break
        fi
        if [[ $i -eq $max_retries ]]; then
            err "Webapp health check failed after $max_retries attempts"
            rollback
        fi
        sleep $retry_delay
    done

    # Check Nginx (if ports 80/443 accessible)
    if curl -sf http://localhost:80 &>/dev/null 2>&1; then
        ok "Nginx health check passed"
    else
        warn "Nginx not responding on port 80 (may need SSL certs)"
    fi
}

# ─── Summary ─────────────────────────────────────────────────
summary() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo -e " ${GREEN}✅ Project Nobi deployed successfully!${NC}"
    echo "═══════════════════════════════════════════════════"
    echo ""
    echo " Environment:  $ENVIRONMENT"
    echo " API:          http://localhost:8042"
    echo " Webapp:       http://localhost:3000"
    echo " Nginx:        http://localhost:80"
    echo ""
    echo " Logs:         $COMPOSE_CMD -f $COMPOSE_FILE logs -f"
    echo " Stop:         $COMPOSE_CMD -f $COMPOSE_FILE down"
    echo " Restart:      $COMPOSE_CMD -f $COMPOSE_FILE restart"
    echo ""
}

# ─── Main ────────────────────────────────────────────────────
main() {
    check_deps
    check_env_file

    if [[ "$ROLLBACK" == "true" ]]; then
        err "Manual rollback requested"
        # Find most recent backup
        BACKUP_TAG=$(docker images --format "{{.Tag}}" nobi-api 2>/dev/null | grep "^backup-" | sort -r | head -1)
        if [[ -n "$BACKUP_TAG" ]]; then
            rollback
        else
            err "No backup images found"
            exit 1
        fi
    fi

    backup_current
    pull_code
    build_and_deploy
    health_check
    summary
}

main "$@"
