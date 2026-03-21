#!/usr/bin/env python3
"""
Weekly Chutes.ai Model Checker
Checks for new/better models and reports recommendations.
Does NOT auto-switch — reports to James for approval.
"""

import os
import sys
import json
import time
import requests

CHUTES_API = "https://llm.chutes.ai/v1"
CHUTES_KEY = os.environ.get("CHUTES_API_KEY", "")
CURRENT_MODEL = os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")

# Models we've tested and trust
KNOWN_GOOD = {
    "deepseek-ai/DeepSeek-V3.1-TEE": {"tier": "primary", "speed": "fast", "quality": 5},
    "deepseek-ai/DeepSeek-V3.2-TEE": {"tier": "backup", "speed": "slow", "quality": 5},
    "Qwen/Qwen3-235B-A22B-Instruct-2507-TEE": {"tier": "fallback", "speed": "medium", "quality": 4},
    "moonshotai/Kimi-K2.5-TEE": {"tier": "tool-calling", "speed": "medium", "quality": 4},
}

# Models to watch for (new releases from top labs)
WATCH_PREFIXES = [
    "deepseek-ai/",
    "Qwen/",
    "moonshotai/",
    "NousResearch/",
    "openai/",
]

def get_available_models():
    """Fetch current model list from Chutes."""
    headers = {"Authorization": f"Bearer {CHUTES_KEY}"}
    try:
        resp = requests.get(f"{CHUTES_API}/models", headers=headers, timeout=10)
        if resp.ok:
            return [m["id"] for m in resp.json().get("data", [])]
    except Exception as e:
        print(f"Error fetching models: {e}")
    return []

def test_model(model_id, prompt="Hello! Tell me a fun fact in one sentence."):
    """Quick speed + quality test."""
    headers = {
        "Authorization": f"Bearer {CHUTES_KEY}",
        "Content-Type": "application/json",
    }
    start = time.time()
    try:
        resp = requests.post(
            f"{CHUTES_API}/chat/completions",
            headers=headers,
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
            },
            timeout=15,
        )
        elapsed = time.time() - start
        if resp.ok:
            text = resp.json()["choices"][0]["message"]["content"]
            return {"speed": round(elapsed, 2), "response": text[:100], "status": "ok"}
        else:
            return {"speed": round(elapsed, 2), "status": f"error_{resp.status_code}"}
    except Exception as e:
        return {"speed": round(time.time() - start, 2), "status": f"error: {e}"}

def main():
    print(f"=== Chutes.ai Model Check — {time.strftime('%Y-%m-%d %H:%M UTC')} ===")
    print(f"Current primary: {CURRENT_MODEL}")
    print()

    models = get_available_models()
    if not models:
        print("ERROR: Could not fetch model list")
        return

    print(f"Total models available: {len(models)}")
    print()

    # Find new models we haven't seen before
    new_models = []
    for m in models:
        if m not in KNOWN_GOOD and any(m.startswith(p) for p in WATCH_PREFIXES):
            new_models.append(m)

    if new_models:
        print(f"🆕 NEW MODELS FOUND ({len(new_models)}):")
        for m in sorted(new_models):
            result = test_model(m)
            status = f"{result['speed']}s" if result["status"] == "ok" else result["status"]
            print(f"  {m} — {status}")
            if result["status"] == "ok":
                print(f"    Response: {result['response']}")
        print()

    # Test current primary
    print("📊 Current primary model test:")
    primary_result = test_model(CURRENT_MODEL)
    if primary_result["status"] == "ok":
        print(f"  {CURRENT_MODEL}: {primary_result['speed']}s ✅")
    else:
        print(f"  {CURRENT_MODEL}: {primary_result['status']} ⚠️")
    print()

    # Check if any new model is faster with good quality
    if new_models:
        print("📋 RECOMMENDATION:")
        fast_new = [m for m in new_models if test_model(m).get("speed", 99) < 3]
        if fast_new:
            print(f"  Consider testing these new fast models: {fast_new}")
            print("  Update CHUTES_MODEL env var and restart bot to switch.")
        else:
            print("  No new models faster than current. Staying with current setup.")
    else:
        print("✅ No new models from watched labs. Current setup is optimal.")

    print()
    print(f"All available models: {', '.join(sorted(models))}")

if __name__ == "__main__":
    if not CHUTES_KEY:
        print("ERROR: CHUTES_API_KEY not set")
        sys.exit(1)
    main()
