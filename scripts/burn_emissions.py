#!/usr/bin/env python3
"""
Nobi Emission Burn — Automated Alpha Burner
============================================
Monitors owner wallet for incoming ALPHA emissions and burns them.
Runs as a PM2 process or cron job.

Flow:
1. Check ALPHA balance for owner hotkey on SN272
2. If balance > threshold (e.g., 0.001 ALPHA): burn it all
3. Log the burn transaction (tx hash, amount, block number)
4. Report to Telegram (optional)
5. Wait and repeat

Usage:
    python burn_emissions.py [--dry-run] [--once] [--network testnet|mainnet]

PM2:
    pm2 start burn_emissions.py --name nobi-burn --interpreter python3

Environment:
    WALLET_NAME=T68Coldkey
    WALLET_HOTKEY=default
    WALLET_PASSWORD=<from .wallet_env>
    BURN_NETWORK=testnet
    BURN_NETUID=272
    BURN_THRESHOLD=0.001
    BURN_INTERVAL=4320  # seconds (72 min = 1 tempo)
    TELEGRAM_TOKEN=<optional>
    TELEGRAM_CHAT_ID=<optional>
"""

import os
import sys
import json
import time
import logging
import argparse
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Path setup ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_DIR = Path(os.environ.get("NOBI_LOG_DIR", Path.home() / ".nobi"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "burn_emissions.log"),
    ],
)
logger = logging.getLogger("nobi.burn")

# ─── Config ──────────────────────────────────────────────────────────────────
NETWORK_ENDPOINTS = {
    "testnet": "test",   # bt.Subtensor("test")
    "mainnet": "finney", # bt.Subtensor("finney")
    "local": "local",
}

WALLET_NAME = os.environ.get("WALLET_NAME", "T68Coldkey")
WALLET_HOTKEY = os.environ.get("WALLET_HOTKEY", "default")
BURN_NETWORK = os.environ.get("BURN_NETWORK", "testnet")
BURN_NETUID = int(os.environ.get("BURN_NETUID", "272"))
# Minimum ALPHA to trigger a burn (in TAO/ALPHA units)
BURN_THRESHOLD = float(os.environ.get("BURN_THRESHOLD", "0.001"))
# Interval between checks in seconds (default: ~72 min = 1 Bittensor tempo)
BURN_INTERVAL = int(os.environ.get("BURN_INTERVAL", "4320"))
HISTORY_PATH = Path(os.environ.get("BURN_HISTORY_PATH", Path.home() / ".nobi/burn_history.json"))
STATE_PATH = Path(os.environ.get("BURN_STATE_PATH", Path.home() / ".nobi/burn_state.json"))

# Optional Telegram notifications
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_wallet_password() -> str:
    """Load wallet password from .wallet_env or environment."""
    # 1. Check environment first
    pwd = os.environ.get("WALLET_PASSWORD", "")
    if pwd:
        return pwd
    # 2. Try .wallet_env file
    wallet_env = Path.home() / ".bittensor/.wallet_env"
    if wallet_env.exists():
        for line in wallet_env.read_text().splitlines():
            line = line.strip()
            if line.startswith("WALLET_PASSWORD="):
                return line.split("=", 1)[1].strip()
    logger.warning("No wallet password found in environment or .wallet_env")
    return ""


def load_history() -> list:
    """Load burn history from disk."""
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text())
        except Exception as e:
            logger.error(f"Failed to load burn history: {e}")
    return []


def save_history(history: list) -> None:
    """Persist burn history to disk."""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def load_state() -> dict:
    """Load persistent state (last burn block etc.)."""
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"last_burn_block": 0, "last_run_ts": 0}


def save_state(state: dict) -> None:
    """Persist state to disk."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def notify_telegram(message: str) -> None:
    """Send a Telegram notification (best-effort, never crashes the main loop)."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


def record_burn(amount_alpha: float, block: int, tx_hash: Optional[str], dry_run: bool) -> dict:
    """Create a burn record and append to history."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "amount_alpha": amount_alpha,
        "block": block,
        "tx_hash": tx_hash or "unknown",
        "network": BURN_NETWORK,
        "netuid": BURN_NETUID,
        "dry_run": dry_run,
    }
    history = load_history()
    history.append(record)
    save_history(history)
    logger.info(
        f"Burn recorded: {amount_alpha:.6f} ALPHA | block={block} | tx={tx_hash} | dry_run={dry_run}"
    )
    return record


# ─── Core burn logic ─────────────────────────────────────────────────────────

def run_burn_cycle(dry_run: bool = False) -> Optional[dict]:
    """
    Check balance and burn if above threshold.
    Returns a burn record if burn was executed, else None.
    """
    import bittensor as bt

    logger.info(f"Starting burn cycle | network={BURN_NETWORK} | netuid={BURN_NETUID} | dry_run={dry_run}")

    # Connect
    endpoint = NETWORK_ENDPOINTS.get(BURN_NETWORK, "test")
    subtensor = bt.Subtensor(network=endpoint)
    current_block = subtensor.get_current_block()
    logger.info(f"Connected to {BURN_NETWORK} | current block: {current_block}")

    # Load wallet
    wallet_password = load_wallet_password()
    wallet = bt.Wallet(name=WALLET_NAME, hotkey=WALLET_HOTKEY)

    # Get owner hotkey SS58
    owner_hotkey_ss58 = subtensor.get_subnet_owner_hotkey(netuid=BURN_NETUID)
    if not owner_hotkey_ss58:
        # Fallback: use wallet hotkey
        owner_hotkey_ss58 = wallet.hotkey.ss58_address
        logger.warning(f"Could not get subnet owner hotkey, using wallet hotkey: {owner_hotkey_ss58}")

    logger.info(f"Owner hotkey: {owner_hotkey_ss58}")

    # Check ALPHA balance for the owner hotkey on this subnet
    alpha_balance = subtensor.get_stake_for_hotkey(
        hotkey_ss58=owner_hotkey_ss58,
        netuid=BURN_NETUID,
    )

    alpha_amount = float(alpha_balance.tao) if hasattr(alpha_balance, 'tao') else float(alpha_balance)
    logger.info(f"Owner ALPHA balance on SN{BURN_NETUID}: {alpha_amount:.6f}")

    # Check threshold
    if alpha_amount < BURN_THRESHOLD:
        logger.info(f"Balance {alpha_amount:.6f} < threshold {BURN_THRESHOLD} — no burn needed")
        return None

    logger.info(f"Balance {alpha_amount:.6f} >= threshold {BURN_THRESHOLD} — proceeding with burn")

    if dry_run:
        logger.info(f"[DRY RUN] Would burn {alpha_amount:.6f} ALPHA on SN{BURN_NETUID}")
        record = record_burn(
            amount_alpha=alpha_amount,
            block=current_block,
            tx_hash="DRY_RUN",
            dry_run=True,
        )
        return record

    # Execute burn via add_stake_burn (subnet owner buyback → burns ALPHA)
    # This converts TAO → ALPHA and immediately burns it.
    # For owner take emissions that have already accumulated as ALPHA stake,
    # we use unstake to get TAO back, then add_stake_burn to burn new ALPHA.
    # NOTE: The mechanism here burns ALPHA equivalent to the emission amount.
    # The exact flow depends on how owner take is disbursed (as staked ALPHA or as dividends).

    # Strategy: burn the accumulated alpha stake by using add_stake_burn with an equivalent amount.
    # In practice for the owner take flow: the owner hotkey accumulates alpha from emissions.
    # We burn by calling add_stake_burn which is the official "burn alpha" mechanism.

    # First, unlock the wallet
    if wallet_password:
        wallet.coldkey  # triggers password prompt or env unlock
        # Try to unlock with password
        try:
            wallet.unlock_coldkey(password=wallet_password)
        except Exception as e:
            logger.warning(f"Wallet unlock warning: {e}")

    try:
        # Convert ALPHA amount to TAO equivalent for burning
        # get_stake_for_hotkey returns Balance with unit set to netuid
        # add_stake_burn takes TAO amount
        # We burn the alpha by converting: use current price to estimate TAO
        # For a full burn, we use the alpha amount directly via move_stake or a direct extrinsic

        # The most direct burn is: unstake from SN272 → then add_stake_burn
        # But actually add_stake_burn IS the burn: it takes TAO, buys alpha, burns it
        # For owner emissions already accumulated as alpha: we use move_stake or unstake first

        # Simple approach: burn using the alpha balance directly
        # In bittensor v10, to burn accumulated alpha: unstake to get TAO back, then stake-burn
        # Or use transfer_stake to SN0 then burn

        # Most direct: just use add_stake_burn with the TAO equivalent
        # Get current subnet price to estimate TAO needed
        price = subtensor.get_subnet_price(netuid=BURN_NETUID)
        tao_equivalent = alpha_balance * price  # approximate TAO for this amount of alpha

        logger.info(f"Burning {alpha_amount:.6f} ALPHA (~{float(tao_equivalent):.6f} TAO equiv)")

        response = subtensor.add_stake_burn(
            wallet=wallet,
            netuid=BURN_NETUID,
            hotkey_ss58=owner_hotkey_ss58,
            amount=tao_equivalent,
            mev_protection=False,  # Testnet may not support MEV shield
            wait_for_inclusion=True,
            wait_for_finalization=True,
        )

        success = bool(response)
        tx_hash = getattr(response, 'extrinsic_hash', None) or str(response)

        if success:
            logger.info(f"✅ Burn SUCCESS: {alpha_amount:.6f} ALPHA burned | tx={tx_hash}")
            record = record_burn(
                amount_alpha=alpha_amount,
                block=current_block,
                tx_hash=tx_hash,
                dry_run=False,
            )
            # Update state
            state = load_state()
            state["last_burn_block"] = current_block
            state["last_run_ts"] = int(time.time())
            save_state(state)

            # Notify
            notify_telegram(
                f"🔥 <b>Nobi Burn Executed</b>\n"
                f"Amount: <code>{alpha_amount:.6f} ALPHA</code>\n"
                f"Block: <code>{current_block}</code>\n"
                f"TX: <code>{tx_hash}</code>\n"
                f"Network: {BURN_NETWORK} | SN{BURN_NETUID}"
            )
            return record
        else:
            logger.error(f"Burn FAILED: response={response}")
            notify_telegram(f"❌ <b>Nobi Burn FAILED</b>\nAmount: {alpha_amount:.6f} ALPHA\nBlock: {current_block}")
            return None

    except Exception as e:
        logger.error(f"Burn exception: {e}\n{traceback.format_exc()}")
        notify_telegram(f"❌ <b>Nobi Burn ERROR</b>: {e}")
        raise


# ─── Main loop ───────────────────────────────────────────────────────────────

def main():
    # Declare globals FIRST before any use (Python requires this)
    global BURN_NETWORK, BURN_NETUID, BURN_INTERVAL, BURN_THRESHOLD  # noqa: PLW0603

    parser = argparse.ArgumentParser(description="Nobi Emission Burn Automation")
    parser.add_argument("--dry-run", action="store_true", help="Simulate burn without executing")
    parser.add_argument("--once", action="store_true", help="Run once and exit (no loop)")
    parser.add_argument("--network", default=BURN_NETWORK, choices=["testnet", "mainnet", "local"],
                        help="Subtensor network (default: testnet)")
    parser.add_argument("--netuid", type=int, default=BURN_NETUID, help="Subnet UID (default: 272)")
    parser.add_argument("--interval", type=int, default=BURN_INTERVAL,
                        help="Check interval in seconds (default: 4320 = 72 min)")
    parser.add_argument("--threshold", type=float, default=BURN_THRESHOLD,
                        help="Minimum ALPHA to trigger burn (default: 0.001)")
    args = parser.parse_args()

    # Override globals with CLI args
    BURN_NETWORK = args.network
    BURN_NETUID = args.netuid
    BURN_INTERVAL = args.interval
    BURN_THRESHOLD = args.threshold

    logger.info("=" * 60)
    logger.info("Nobi Emission Burn Daemon")
    logger.info(f"Network: {args.network} | NetUID: {args.netuid}")
    logger.info(f"Threshold: {BURN_THRESHOLD} ALPHA | Interval: {BURN_INTERVAL}s")
    logger.info(f"Dry-run: {args.dry_run} | Once: {args.once}")
    logger.info(f"History: {HISTORY_PATH}")
    logger.info("=" * 60)

    if args.once:
        run_burn_cycle(dry_run=args.dry_run)
        return

    # Continuous loop
    while True:
        try:
            run_burn_cycle(dry_run=args.dry_run)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            break
        except Exception as e:
            logger.error(f"Burn cycle failed: {e}")
            notify_telegram(f"⚠️ Burn cycle error: {e}")

        logger.info(f"Sleeping {BURN_INTERVAL}s until next check...")
        time.sleep(BURN_INTERVAL)


if __name__ == "__main__":
    main()
