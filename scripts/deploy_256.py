#!/usr/bin/env python3
"""
deploy_256.py — Project Nobi 256-Neuron Deployment Script
==========================================================
Registers and deploys 256 neurons (20 validators + 236 miners) across 6 servers
on Bittensor testnet subnet 272.

Phases:
  1. Generate hotkeys (on Hetzner1)
  2. Register all UIDs via burn registration (resume-safe)
  3. Distribute hotkeys + generate PM2 ecosystem configs per server
  4. Start all PM2 processes on target servers

Usage:
  python3 deploy_256.py --phase all          # Run all phases
  python3 deploy_256.py --phase hotkeys      # Phase 1 only
  python3 deploy_256.py --phase register     # Phase 2 only
  python3 deploy_256.py --phase distribute   # Phase 3 only
  python3 deploy_256.py --phase start        # Phase 4 only
  python3 deploy_256.py --dry-run            # Preview without executing
  python3 deploy_256.py --status             # Show current state

Safe to re-run at any point — idempotent design.
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_DIR = SCRIPT_DIR.parent
STATE_FILE = SCRIPT_DIR / "deploy_256_state.json"
KEYS_FILE = SCRIPT_DIR / "chutes_keys.txt"
SERVER_CONFIG_FILE = SCRIPT_DIR / "server_config.json"
LOG_FILE = SCRIPT_DIR / "deploy_256.log"

NETUID = 272
NETWORK = "test"
WALLET_NAME = "T68Coldkey"
WALLET_PATH = os.path.expanduser("~/.bittensor/wallets")

CHUTES_MODEL = (
    "deepseek-ai/DeepSeek-V3.1-TEE,"
    "deepseek-ai/DeepSeek-V3,"
    "openai/gpt-oss-120b-TEE,"
    "chutesai/Mistral-Small-3.2-24B-Instruct-2506:latency"
)

MINER_COUNT = 236
VAL_COUNT = 20
TOTAL_NEURONS = MINER_COUNT + VAL_COUNT  # 256

# Port ranges
MINER_PORT_BASE = 9000  # 9000 – 9999
VAL_PORT_BASE = 8000    # 8000 – 8099

# Registration timing (1 block ≈ 12s; use 14s to be safe)
REG_DELAY_SECONDS = 4380

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

# Import bittensor FIRST — it overrides the root logger on import
import bittensor as bt

def setup_logging():
    """Set up logging AFTER bittensor import (bt overrides root logger)."""
    # Remove all handlers bittensor added
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.INFO)
    logging.root.addHandler(stream_handler)
    logging.root.addHandler(file_handler)
    logging.root.setLevel(logging.INFO)
    for h in logging.root.handlers:
        h.setFormatter(logging.Formatter(fmt))
    # Suppress bittensor's verbose logging
    logging.getLogger("bittensor").setLevel(logging.WARNING)

log = logging.getLogger("deploy_256")

# ──────────────────────────────────────────────────────────────────────────────
# State management
# ──────────────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load deployment state from JSON file."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hotkeys_generated": [],
        "registrations": {},   # hotkey_name -> {"uid": int, "cost": float, "ts": str}
        "distributed": [],     # server names that received hotkeys
        "started": [],         # server names that have PM2 running
        "phase_completed": [],
    }

def save_state(state: dict):
    """Persist state to disk atomically."""
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(STATE_FILE)

def load_server_config() -> dict:
    with open(SERVER_CONFIG_FILE) as f:
        return json.load(f)

def load_chutes_keys() -> list[str]:
    """Load API keys from chutes_keys.txt (one per line, strips blanks/comments)."""
    if not KEYS_FILE.exists():
        log.warning(f"Keys file not found: {KEYS_FILE}. Using empty list.")
        return []
    keys = []
    with open(KEYS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                keys.append(line)
    log.info(f"Loaded {len(keys)} Chutes API keys")
    return keys

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def run_cmd(cmd: list[str], check=True, capture=False) -> subprocess.CompletedProcess:
    """Run a shell command with logging."""
    log.debug(f"CMD: {' '.join(str(c) for c in cmd)}")
    kwargs = {"check": check}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    result = subprocess.run(cmd, **kwargs)
    return result

def ssh_run(host: str, command: str, check=True) -> subprocess.CompletedProcess:
    """Run a command on a remote server via SSH."""
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=30",
        host, command
    ]
    log.debug(f"SSH [{host}]: {command}")
    return subprocess.run(
        ssh_cmd,
        capture_output=True,
        text=True,
        check=check,
    )

def hotkey_path(hotkey_name: str) -> Path:
    """Return the path to a hotkey JSON file."""
    return Path(WALLET_PATH) / WALLET_NAME / "hotkeys" / hotkey_name

def hotkey_exists(hotkey_name: str) -> bool:
    return hotkey_path(hotkey_name).exists()

def with_retry(fn, retries=3, delay=5, label="operation"):
    """Retry a function up to `retries` times on exception."""
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == retries:
                log.error(f"{label} failed after {retries} attempts: {e}")
                raise
            log.warning(f"{label} attempt {attempt}/{retries} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)

# ──────────────────────────────────────────────────────────────────────────────
# Phase 1: Generate Hotkeys
# ──────────────────────────────────────────────────────────────────────────────

def generate_hotkeys(state: dict, dry_run: bool = False) -> dict:
    """
    Phase 1: Create all hotkeys under T68Coldkey.
    Skips any that already exist.
    """
    log.info("=" * 60)
    log.info("PHASE 1: Generating hotkeys")
    log.info("=" * 60)

    all_hotkeys = []
    for i in range(1, VAL_COUNT + 1):
        all_hotkeys.append(f"nobi-val-{i:03d}")
    for i in range(1, MINER_COUNT + 1):
        all_hotkeys.append(f"nobi-miner-{i:03d}")

    created = 0
    skipped = 0

    for hk_name in all_hotkeys:
        if hotkey_exists(hk_name):
            log.info(f"  [SKIP] {hk_name} — already exists")
            skipped += 1
            if hk_name not in state["hotkeys_generated"]:
                state["hotkeys_generated"].append(hk_name)
            continue

        if dry_run:
            log.info(f"  [DRY-RUN] Would create hotkey: {hk_name}")
            created += 1
            continue

        log.info(f"  [CREATE] {hk_name}")
        try:
            wallet = bt.Wallet(name=WALLET_NAME, hotkey=hk_name, path=WALLET_PATH)
            wallet.create_new_hotkey(use_password=False, overwrite=False)
            if hk_name not in state["hotkeys_generated"]:
                state["hotkeys_generated"].append(hk_name)
            created += 1
            save_state(state)
        except Exception as e:
            log.error(f"  [ERROR] Failed to create {hk_name}: {e}")
            raise

    log.info(f"Phase 1 complete: {created} created, {skipped} skipped")
    if not dry_run and "hotkeys" not in state["phase_completed"]:
        state["phase_completed"].append("hotkeys")
        save_state(state)
    return state

# ──────────────────────────────────────────────────────────────────────────────
# Phase 2: Register All UIDs
# ──────────────────────────────────────────────────────────────────────────────

def get_registered_hotkeys(subtensor) -> dict:
    """Return {ss58_address: uid} for all neurons on SN272."""
    neurons = subtensor.neurons(netuid=NETUID)
    return {n.hotkey: n.uid for n in neurons}

def register_hotkeys(state: dict, dry_run: bool = False) -> dict:
    """
    Phase 2: Register each hotkey on testnet SN272 via burn registration.
    Resume-safe: checks state and on-chain registry before each registration.
    """
    log.info("=" * 60)
    log.info("PHASE 2: Registering hotkeys on SN272 (testnet)")
    log.info("=" * 60)

    # Build full ordered list: validators first, then miners
    all_hotkeys = []
    for i in range(1, VAL_COUNT + 1):
        all_hotkeys.append(f"nobi-val-{i:03d}")
    for i in range(1, MINER_COUNT + 1):
        all_hotkeys.append(f"nobi-miner-{i:03d}")

    if dry_run:
        log.info(f"[DRY-RUN] Would register {len(all_hotkeys)} hotkeys on netuid {NETUID}")
        for hk in all_hotkeys:
            already = state["registrations"].get(hk)
            status = f"already registered (uid={already['uid']})" if already else "needs registration"
            log.info(f"  {hk}: {status}")
        return state

    subtensor = bt.Subtensor(network=NETWORK)
    coldkey_wallet = bt.Wallet(name=WALLET_NAME, path=WALLET_PATH)

    # Decrypt coldkey using password from env file
    _pw_file = Path(WALLET_PATH).parent / ".wallet_env"
    _pw = ""
    if _pw_file.exists():
        for line in _pw_file.read_text().splitlines():
            if line.startswith("WALLET_PASSWORD="):
                _pw = line.split("=", 1)[1].strip()
    if not _pw:
        _pw = os.environ.get("WALLET_PASSWORD", "")
    if _pw:
        coldkey_wallet.coldkey_file.save_password_to_env(_pw)
        log.info("Coldkey password loaded")

    log.info("Fetching current on-chain neuron registry...")
    registered = get_registered_hotkeys(subtensor)
    log.info(f"Currently {len(registered)} neurons registered on SN{NETUID}")

    # Map hotkey name → ss58 address
    def get_hotkey_ss58(hk_name: str) -> str:
        hk_file = hotkey_path(hk_name)
        with open(hk_file) as f:
            data = json.load(f)
        return data["ss58Address"]

    total_to_register = 0
    for hk_name in all_hotkeys:
        if hk_name not in state["registrations"]:
            if not hotkey_exists(hk_name):
                log.warning(f"  Hotkey file missing for {hk_name} — skipping registration")
                continue
            ss58 = get_hotkey_ss58(hk_name)
            if ss58 not in registered:
                total_to_register += 1

    log.info(f"Need to register: {total_to_register} hotkeys")
    if total_to_register > 0:
        est_minutes = (total_to_register * REG_DELAY_SECONDS) / 60
        log.info(f"Estimated time: ~{est_minutes:.0f} minutes ({total_to_register} blocks)")

    registered_count = 0
    for idx, hk_name in enumerate(all_hotkeys):
        # Check state cache first
        if hk_name in state["registrations"]:
            log.info(f"  [SKIP] {hk_name} — already in state (uid={state['registrations'][hk_name]['uid']})")
            continue

        if not hotkey_exists(hk_name):
            log.warning(f"  [WARN] {hk_name} — hotkey file missing, skipping")
            continue

        ss58 = get_hotkey_ss58(hk_name)

        # Re-fetch registry periodically to catch any changes
        if registered_count % 10 == 0:
            log.info("  Refreshing on-chain registry...")
            registered = get_registered_hotkeys(subtensor)

        if ss58 in registered:
            uid = registered[ss58]
            log.info(f"  [ON-CHAIN] {hk_name} already registered (uid={uid})")
            state["registrations"][hk_name] = {
                "uid": uid,
                "cost": 0.0,
                "ts": datetime.now(timezone.utc).isoformat(),
                "ss58": ss58,
            }
            save_state(state)
            continue

        # Get burn cost
        try:
            burn_cost = subtensor.burn(netuid=NETUID)
            burn_tau = float(burn_cost) / 1e9
            log.info(f"  [REGISTER] {hk_name} | burn cost: τ{burn_tau:.4f}")
        except Exception as e:
            log.warning(f"  Could not get burn cost: {e}, proceeding anyway")
            burn_tau = 0.021

        def do_register():
            hotkey_wallet = bt.Wallet(name=WALLET_NAME, hotkey=hk_name, path=WALLET_PATH)
            if _pw:
                hotkey_wallet.coldkey_file.save_password_to_env(_pw)
            success = subtensor.burned_register(
                wallet=hotkey_wallet,
                netuid=NETUID,
                wait_for_inclusion=True,
                wait_for_finalization=True,
            )
            return success

        try:
            result = with_retry(do_register, retries=3, delay=20, label=f"register {hk_name}")
        except Exception as e:
            log.error(f"  [FAILED] {hk_name}: {e}")
            # Wait before trying next to avoid rate limit
            time.sleep(REG_DELAY_SECONDS)
            continue

        # Verify registration actually succeeded on-chain
        time.sleep(5)
        registered = get_registered_hotkeys(subtensor)
        uid = registered.get(ss58, -1)

        if uid != -1:
            log.info(f"  [OK] {hk_name} → uid={uid} | cost=τ{burn_tau:.4f}")
            state["registrations"][hk_name] = {
                "uid": uid,
                "cost": burn_tau,
                "ts": datetime.now(timezone.utc).isoformat(),
                "ss58": ss58,
            }
            registered_count += 1
            save_state(state)
        else:
            log.error(f"  [FAIL-VERIFY] {hk_name} — not found on-chain after register call")

        # Wait for next block (1 registration per block max)
        if idx < len(all_hotkeys) - 1:
            log.info(f"  Waiting {REG_DELAY_SECONDS}s for next block...")
            time.sleep(REG_DELAY_SECONDS)

    log.info(f"Phase 2 complete: {registered_count} newly registered")
    if "register" not in state["phase_completed"]:
        state["phase_completed"].append("register")
    save_state(state)
    return state

# ──────────────────────────────────────────────────────────────────────────────
# Phase 3: Distribute to Servers
# ──────────────────────────────────────────────────────────────────────────────

def generate_pm2_ecosystem(server: dict, miners: list[dict], validators: list[dict]) -> str:
    """
    Generate a PM2 ecosystem.config.js for a server.
    
    miners/validators are lists of dicts with keys:
      name, hotkey_name, port, chutes_key
    """
    apps = []

    # Validators
    for v in validators:
        app = f"""  {{
    name: "{v['name']}",
    script: "python3",
    args: [
      "neurons/validator.py",
      "--netuid", "272",
      "--subtensor.network", "test",
      "--wallet.name", "T68Coldkey",
      "--wallet.hotkey", "{v['hotkey_name']}",
      "--axon.port", "{v['port']}",
      "--logging.debug"
    ],
    cwd: "{server['repo_path']}",
    interpreter: "none",
    env: {{
      CHUTES_API_KEY: "{v['chutes_key']}",
      CHUTES_MODEL: "{CHUTES_MODEL}"
    }},
    restart_delay: 5000,
    max_restarts: 10,
    autorestart: true,
    watch: false,
    log_date_format: "YYYY-MM-DD HH:mm:ss"
  }}"""
        apps.append(app)

    # Miners
    for m in miners:
        app = f"""  {{
    name: "{m['name']}",
    script: "python3",
    args: [
      "neurons/miner.py",
      "--netuid", "272",
      "--subtensor.network", "test",
      "--wallet.name", "T68Coldkey",
      "--wallet.hotkey", "{m['hotkey_name']}",
      "--axon.port", "{m['port']}",
      "--logging.debug"
    ],
    cwd: "{server['repo_path']}",
    interpreter: "none",
    env: {{
      CHUTES_API_KEY: "{m['chutes_key']}",
      CHUTES_MODEL: "{CHUTES_MODEL}"
    }},
    restart_delay: 5000,
    max_restarts: 10,
    autorestart: true,
    watch: false,
    log_date_format: "YYYY-MM-DD HH:mm:ss"
  }}"""
        apps.append(app)

    apps_str = ",\n".join(apps)
    ecosystem = f"""// PM2 Ecosystem Config — {server['name']}
// Generated by deploy_256.py on {datetime.now(timezone.utc).isoformat()}
// DO NOT EDIT MANUALLY — regenerate with: python3 scripts/deploy_256.py --phase distribute

module.exports = {{
  apps: [
{apps_str}
  ]
}};
"""
    return ecosystem

def distribute_to_servers(state: dict, dry_run: bool = False) -> dict:
    """
    Phase 3: SCP hotkeys to servers, generate PM2 ecosystem configs.
    """
    log.info("=" * 60)
    log.info("PHASE 3: Distributing hotkeys to servers")
    log.info("=" * 60)

    config = load_server_config()
    api_keys = load_chutes_keys()

    if not api_keys:
        log.error("No Chutes API keys found. Cannot proceed with distribution.")
        raise ValueError("No API keys loaded from chutes_keys.txt")

    # Round-robin key index (global across all neurons)
    key_idx = 0

    for server in config["servers"]:
        srv_name = server["name"]
        ssh_host = server["ssh_host"]
        m_start = server["miner_start_idx"]
        m_end = server["miner_end_idx"]
        v_start = server["val_start_idx"]
        v_end = server["val_end_idx"]
        m_port_base = server["miner_port_start"]
        v_port_base = server["val_port_start"]

        log.info(f"\n--- {srv_name} ({ssh_host}) ---")

        # Build miner list
        miners = []
        for local_idx, global_idx in enumerate(range(m_start, m_end + 1)):
            hk_name = f"nobi-miner-{global_idx:03d}"
            port = m_port_base + local_idx
            chutes_key = api_keys[key_idx % len(api_keys)]
            key_idx += 1
            miners.append({
                "name": f"nobi-miner-{global_idx:03d}",
                "hotkey_name": hk_name,
                "port": port,
                "chutes_key": chutes_key,
            })

        # Build validator list
        validators = []
        for local_idx, global_idx in enumerate(range(v_start, v_end + 1)):
            hk_name = f"nobi-val-{global_idx:03d}"
            port = v_port_base + local_idx
            chutes_key = api_keys[key_idx % len(api_keys)]
            key_idx += 1
            validators.append({
                "name": f"nobi-val-{global_idx:03d}",
                "hotkey_name": hk_name,
                "port": port,
                "chutes_key": chutes_key,
            })

        log.info(f"  Miners: {len(miners)} ({m_start}–{m_end}), "
                 f"Validators: {len(validators)} ({v_start}–{v_end})")

        # Generate PM2 ecosystem config
        ecosystem_content = generate_pm2_ecosystem(server, miners, validators)
        ecosystem_local = SCRIPT_DIR / f"ecosystem_{srv_name}.config.js"

        if not dry_run:
            with open(ecosystem_local, "w") as f:
                f.write(ecosystem_content)
            log.info(f"  Written: {ecosystem_local}")
        else:
            log.info(f"  [DRY-RUN] Would write ecosystem config: {ecosystem_local}")

        if dry_run:
            log.info(f"  [DRY-RUN] Would SCP {len(miners) + len(validators)} hotkeys to {ssh_host}")
            log.info(f"  [DRY-RUN] Would SCP ecosystem config to {ssh_host}:{server['repo_path']}/ecosystem.config.js")
            continue

        # Create remote wallet directory
        remote_hotkeys_dir = f"/root/.bittensor/wallets/{WALLET_NAME}/hotkeys"
        log.info(f"  Creating remote hotkeys dir: {remote_hotkeys_dir}")
        try:
            result = ssh_run(ssh_host, f"mkdir -p {remote_hotkeys_dir}", check=False)
            if result.returncode != 0:
                log.warning(f"  mkdir warning: {result.stderr.strip()}")
        except Exception as e:
            log.error(f"  SSH error creating directory: {e}")
            continue

        # SCP all hotkeys for this server
        all_hk_names = [m["hotkey_name"] for m in miners] + [v["hotkey_name"] for v in validators]
        log.info(f"  SCPing {len(all_hk_names)} hotkey files...")

        failed_scp = []
        for hk_name in all_hk_names:
            hk_file = hotkey_path(hk_name)
            if not hk_file.exists():
                log.warning(f"  [WARN] Hotkey file not found: {hk_file} — skipping")
                failed_scp.append(hk_name)
                continue

            def do_scp(hk_file=hk_file, hk_name=hk_name):
                scp_cmd = [
                    "scp", "-o", "StrictHostKeyChecking=no",
                    "-o", "ConnectTimeout=30",
                    str(hk_file),
                    f"{ssh_host}:{remote_hotkeys_dir}/{hk_name}"
                ]
                result = subprocess.run(scp_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"SCP failed: {result.stderr.strip()}")

            try:
                with_retry(do_scp, retries=3, delay=5, label=f"scp {hk_name}")
            except Exception as e:
                log.error(f"  [ERROR] SCP {hk_name}: {e}")
                failed_scp.append(hk_name)

        if failed_scp:
            log.warning(f"  {len(failed_scp)} hotkeys failed to SCP: {failed_scp[:5]}{'...' if len(failed_scp) > 5 else ''}")
        else:
            log.info(f"  All {len(all_hk_names)} hotkeys SCP'd successfully")

        # SCP ecosystem config
        remote_ecosystem = f"{server['repo_path']}/ecosystem.config.js"
        def do_scp_ecosystem():
            scp_cmd = [
                "scp", "-o", "StrictHostKeyChecking=no",
                str(ecosystem_local),
                f"{ssh_host}:{remote_ecosystem}"
            ]
            result = subprocess.run(scp_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"SCP failed: {result.stderr.strip()}")

        try:
            with_retry(do_scp_ecosystem, retries=3, delay=5, label=f"scp ecosystem {srv_name}")
            log.info(f"  Ecosystem config deployed to {ssh_host}:{remote_ecosystem}")
        except Exception as e:
            log.error(f"  [ERROR] Failed to SCP ecosystem config to {srv_name}: {e}")
            continue

        # Clone/update repo on server
        log.info(f"  Ensuring repo exists at {server['repo_path']}...")
        clone_cmd = (
            f"if [ -d '{server['repo_path']}' ]; then "
            f"  cd '{server['repo_path']}' && git pull --quiet; "
            f"else "
            f"  git clone https://github.com/ProjectNobi/project-nobi.git '{server['repo_path']}'; "
            f"fi"
        )
        try:
            result = ssh_run(ssh_host, clone_cmd, check=False)
            if result.returncode == 0:
                log.info(f"  Repo OK")
            else:
                log.warning(f"  Repo update warning: {result.stderr.strip()[:200]}")
        except Exception as e:
            log.warning(f"  Repo check failed (non-fatal): {e}")

        # Install dependencies on server
        log.info(f"  Installing/verifying dependencies...")
        pip_cmd = f"cd '{server['repo_path']}' && pip install -r requirements.txt -q 2>/dev/null || true"
        try:
            ssh_run(ssh_host, pip_cmd, check=False)
        except Exception as e:
            log.warning(f"  pip install warning: {e}")

        if srv_name not in state["distributed"]:
            state["distributed"].append(srv_name)
        save_state(state)
        log.info(f"  ✓ {srv_name} distribution complete")

    log.info(f"\nPhase 3 complete: {len(state['distributed'])} servers distributed")
    if "distribute" not in state["phase_completed"]:
        state["phase_completed"].append("distribute")
    save_state(state)
    return state

# ──────────────────────────────────────────────────────────────────────────────
# Phase 4: Start All Processes
# ──────────────────────────────────────────────────────────────────────────────

def start_processes(state: dict, dry_run: bool = False) -> dict:
    """
    Phase 4: SSH to each server and start PM2 ecosystem.
    """
    log.info("=" * 60)
    log.info("PHASE 4: Starting PM2 processes on all servers")
    log.info("=" * 60)

    config = load_server_config()

    for server in config["servers"]:
        srv_name = server["name"]
        ssh_host = server["ssh_host"]
        repo_path = server["repo_path"]

        log.info(f"\n--- {srv_name} ({ssh_host}) ---")

        if dry_run:
            log.info(f"  [DRY-RUN] Would run: pm2 start {repo_path}/ecosystem.config.js")
            continue

        # Install PM2 if not present
        pm2_check = ssh_run(ssh_host, "which pm2 || npm install -g pm2 2>&1 | tail -1", check=False)
        log.info(f"  PM2 check: {pm2_check.stdout.strip()[:100]}")

        # Start/reload PM2 ecosystem
        start_cmd = (
            f"cd '{repo_path}' && "
            f"pm2 start ecosystem.config.js --env production 2>&1 || "
            f"pm2 reload ecosystem.config.js 2>&1"
        )

        def do_start(start_cmd=start_cmd, ssh_host=ssh_host):
            result = ssh_run(ssh_host, start_cmd, check=False)
            if result.returncode != 0 and "already launched" not in result.stdout:
                raise RuntimeError(f"PM2 start failed: {result.stderr[:200]}")
            return result

        try:
            result = with_retry(do_start, retries=2, delay=10, label=f"pm2 start {srv_name}")
            log.info(f"  PM2 output: {result.stdout.strip()[:300]}")
        except Exception as e:
            log.error(f"  [ERROR] Failed to start PM2 on {srv_name}: {e}")
            continue

        # Save PM2 process list
        ssh_run(ssh_host, "pm2 save 2>/dev/null || true", check=False)

        # Verify processes
        time.sleep(5)
        status_result = ssh_run(ssh_host, "pm2 list --no-color 2>/dev/null | grep -c online || echo 0", check=False)
        online_count = status_result.stdout.strip()
        log.info(f"  Online processes: {online_count}")

        if srv_name not in state["started"]:
            state["started"].append(srv_name)
        save_state(state)
        log.info(f"  ✓ {srv_name} started")

    log.info(f"\nPhase 4 complete: {len(state['started'])} servers running")
    if "start" not in state["phase_completed"]:
        state["phase_completed"].append("start")
    save_state(state)
    return state

# ──────────────────────────────────────────────────────────────────────────────
# Status Report
# ──────────────────────────────────────────────────────────────────────────────

def show_status(state: dict):
    """Print a human-readable status report."""
    log.info("=" * 60)
    log.info("DEPLOYMENT STATUS")
    log.info("=" * 60)
    log.info(f"State file: {STATE_FILE}")
    log.info(f"Created: {state.get('created_at', 'unknown')}")
    log.info(f"Phases completed: {state.get('phase_completed', [])}")
    log.info(f"Hotkeys generated: {len(state.get('hotkeys_generated', []))}/{TOTAL_NEURONS}")
    log.info(f"Registrations: {len(state.get('registrations', {}))}/{TOTAL_NEURONS}")
    log.info(f"Servers distributed: {state.get('distributed', [])}")
    log.info(f"Servers started: {state.get('started', [])}")

    regs = state.get("registrations", {})
    if regs:
        total_cost = sum(v.get("cost", 0) for v in regs.values())
        log.info(f"Total registration cost: τ{total_cost:.4f}")

        miners_reg = [k for k in regs if "miner" in k]
        vals_reg = [k for k in regs if "val" in k]
        log.info(f"  Validators registered: {len(vals_reg)}/{VAL_COUNT}")
        log.info(f"  Miners registered: {len(miners_reg)}/{MINER_COUNT}")

    # Missing registrations
    all_expected = (
        [f"nobi-val-{i:03d}" for i in range(1, VAL_COUNT + 1)] +
        [f"nobi-miner-{i:03d}" for i in range(1, MINER_COUNT + 1)]
    )
    missing = [h for h in all_expected if h not in regs]
    if missing:
        log.info(f"  Missing registrations: {len(missing)} (first 5: {missing[:5]})")

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Deploy 256 neurons (20 validators + 236 miners) for Project Nobi on SN272 testnet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--phase",
        choices=["all", "hotkeys", "register", "distribute", "start"],
        default="all",
        help="Which phase to run (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without executing anything",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current deployment status and exit",
    )
    parser.add_argument(
        "--reset-phase",
        choices=["hotkeys", "register", "distribute", "start"],
        help="Remove a phase from completed list to re-run it",
    )
    args = parser.parse_args()

    state = load_state()

    if args.reset_phase:
        if args.reset_phase in state["phase_completed"]:
            state["phase_completed"].remove(args.reset_phase)
            save_state(state)
            log.info(f"Reset phase '{args.reset_phase}' — it will run again")
        return

    if args.status:
        show_status(state)
        return

    if args.dry_run:
        log.info("[DRY-RUN MODE] No changes will be made")

    log.info(f"Starting deployment | phase={args.phase} | dry_run={args.dry_run}")
    log.info(f"Target: {TOTAL_NEURONS} neurons ({VAL_COUNT} validators + {MINER_COUNT} miners)")
    log.info(f"Subnet: {NETUID} ({NETWORK})")
    log.info(f"Wallet: {WALLET_NAME}")

    run_hotkeys = args.phase in ("all", "hotkeys")
    run_register = args.phase in ("all", "register")
    run_distribute = args.phase in ("all", "distribute")
    run_start = args.phase in ("all", "start")

    if run_hotkeys:
        state = generate_hotkeys(state, dry_run=args.dry_run)

    if run_register:
        state = register_hotkeys(state, dry_run=args.dry_run)

    if run_distribute:
        state = distribute_to_servers(state, dry_run=args.dry_run)

    if run_start:
        state = start_processes(state, dry_run=args.dry_run)

    show_status(state)
    log.info("Deployment script finished.")


if __name__ == "__main__":
    main()
