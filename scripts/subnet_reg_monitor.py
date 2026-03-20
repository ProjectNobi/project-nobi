#!/usr/bin/env python3
"""
Subnet Registration Cost Monitor — Checks mainnet subnet registration cost.
Alerts when cost drops below target (300 TAO).
Runs via cron every 6 hours.
"""
import os
import sys
import json
from datetime import datetime, timezone

TARGET_COST = 300  # TAO
HISTORY_FILE = os.path.expanduser("~/.nobi/subnet_reg_history.json")

def get_registration_cost():
    """Get current subnet registration cost from mainnet."""
    try:
        import bittensor as bt
        sub = bt.Subtensor(network="finney")
        cost = sub.get_subnet_burn_cost()
        # Convert from RAO to TAO
        if hasattr(cost, 'tao'):
            return float(cost.tao)
        return float(cost) / 1e9
    except Exception as e:
        print(f"Error getting cost: {e}")
        return None

def load_history():
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"checks": [], "lowest": None, "alerts_sent": 0}

def save_history(data):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    cost = get_registration_cost()
    
    if cost is None:
        print(f"[{now}] ❌ Failed to get subnet registration cost")
        return
    
    history = load_history()
    
    # Track history (keep last 100 entries)
    history["checks"].append({"time": now, "cost": cost})
    history["checks"] = history["checks"][-100:]
    
    # Track lowest
    if history["lowest"] is None or cost < history["lowest"]:
        history["lowest"] = cost
    
    # Calculate trend
    trend = ""
    if len(history["checks"]) >= 2:
        prev = history["checks"][-2]["cost"]
        diff = cost - prev
        if diff > 0:
            trend = f"📈 +{diff:.1f} TAO"
        elif diff < 0:
            trend = f"📉 {diff:.1f} TAO"
        else:
            trend = "➡️ unchanged"
    
    # Print report
    print(f"# 📊 Subnet Registration Cost — {now}")
    print(f"")
    print(f"**Current cost:** {cost:.1f} TAO")
    print(f"**Target:** {TARGET_COST} TAO")
    print(f"**Lowest recorded:** {history['lowest']:.1f} TAO")
    print(f"**Trend:** {trend}")
    print(f"**Checks:** {len(history['checks'])}")
    
    if cost <= TARGET_COST:
        print(f"")
        print(f"🚨🚨🚨 **ALERT: BELOW TARGET!** 🚨🚨🚨")
        print(f"**Registration cost is {cost:.1f} TAO — BELOW our {TARGET_COST} TAO target!**")
        print(f"**ACTION: Consider registering Project Nobi mainnet subnet NOW!**")
        history["alerts_sent"] = history.get("alerts_sent", 0) + 1
    elif cost <= TARGET_COST * 1.2:  # Within 20% of target
        print(f"")
        print(f"⚠️ **Getting close!** Cost is within 20% of target ({cost:.1f} vs {TARGET_COST} TAO)")
    else:
        print(f"")
        print(f"💤 Still above target. Gap: {cost - TARGET_COST:.1f} TAO")
    
    save_history(history)

if __name__ == "__main__":
    main()
