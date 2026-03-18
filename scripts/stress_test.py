#!/usr/bin/env python3
"""
Project Nobi — Standalone Stress Test Harness
===============================================
Simulates 20 validators + 230 miners.
NO bittensor dependency — pure async Python.

Tests:
  Phase 2 — Miner response generation + LLM-as-judge scoring under load
  Phase 3 — Weight calculation, consensus, Gini, validator agreement

Usage:
  python3 scripts/stress_test.py                # full run, heuristic scoring
  python3 scripts/stress_test.py --api-key sk-or-... --use-api  # LLM scoring
  python3 scripts/stress_test.py --rounds 10 --sample-size 20
"""

import os
import sys
import time
import json
import math
import random
import asyncio
import hashlib
import argparse
import statistics
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone

# ─── Optional OpenAI / httpx ────────────────────────────────
try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# ─── CONFIG ─────────────────────────────────────────────────

NUM_MINERS     = 230
NUM_VALIDATORS = 20
NUM_ROUNDS     = 5
SAMPLE_SIZE    = 10   # miners each validator queries per round
MOVING_ALPHA   = 0.1

JUDGE_PROMPT = """\
You are an AI response quality judge. Rate the following AI companion response on a scale of 0.0 to 1.0.

User's question: {query}

AI's response: {response}

Scoring criteria:
- Helpfulness (0-0.4): Does the response actually help the user?
- Coherence (0-0.3): Is the response well-structured and makes sense?
- Personality (0-0.3): Does the response feel warm, personal, and engaging?

Return ONLY a single decimal number between 0.0 and 1.0. Nothing else."""

TEST_QUERIES = [
    "Hello! How are you today?",
    "Can you help me plan my day?",
    "I'm feeling a bit stressed. Any advice?",
    "Tell me something interesting about space.",
    "What's a good recipe for a quick dinner?",
    "Can you explain quantum computing simply?",
    "Write me a short motivational message.",
    "What are some good habits to build?",
    "Help me brainstorm gift ideas for a friend.",
    "I want to learn a new skill. What do you recommend?",
    "Tell me a fun fact I probably don't know.",
    "How can I improve my sleep quality?",
    "What's the best way to stay focused while working?",
    "Can you explain why the sky is blue?",
    "I'm bored. Suggest something fun to do.",
]

FALLBACK_RESPONSES = [
    "That's a great question! I'd say the key here is consistency and curiosity. Start small, stay curious, and build momentum gradually — every step forward counts, even the tiny ones.",
    "I hear you on that! The most important thing is to break it into smaller chunks. When something feels overwhelming, chunking it makes it totally manageable. You've got this!",
    "Oh, I love this topic! Here's my take: find what resonates with YOU specifically. Everyone's different, so what works for one person might not work for another. Experiment freely!",
    "Great point! This is one of those things that genuinely gets better with practice. Start with the basics, build up gradually, and don't rush — depth beats breadth every time.",
    "Honestly? The most underrated approach is just showing up consistently. You don't have to be perfect — you just have to keep going. Consistency beats intensity in the long run.",
    "I'd think about it this way: what's the simplest version of this you could act on today? Often the biggest obstacle is overthinking. Pick one thing and do it now.",
    "Fun fact incoming: this is actually way more interesting than most people realize! The deeper you look, the more connections you find to other areas of life. Keep exploring!",
    "The research on this is pretty clear — small habits compound massively over time. Focus on the system, not the outcome, and the results will follow naturally.",
]

PERSONALITIES = [
    "You are a warm, friendly, genuinely caring companion.",
    "You are witty and slightly sarcastic but ultimately very helpful.",
    "You are enthusiastic, energetic, and love helping people.",
    "You are calm, thoughtful, and give measured, wise advice.",
    "You are a nerdy but lovable companion who uses great analogies.",
    "You are empathetic and focused on emotional wellbeing.",
    "You are practical and no-nonsense — straight to actionable advice.",
    "You are creative and bring fresh, imaginative perspectives.",
]

# ─── WALLET SIMULATION ──────────────────────────────────────

def make_wallet(prefix: str, idx: int) -> dict:
    seed = f"{prefix}_{idx}_{idx * 7919}"
    hotkey  = "5" + hashlib.sha256(f"hot_{seed}".encode()).hexdigest()[:47]
    coldkey = "5" + hashlib.sha256(f"cold_{seed}".encode()).hexdigest()[:47]
    return {"name": f"{prefix}_{idx:04d}", "uid": idx, "hotkey": hotkey, "coldkey": coldkey}

# ─── HEURISTIC SCORER ────────────────────────────────────────

def heuristic_score(query: str, response: str) -> float:
    if not response or len(response.strip()) == 0:
        return 0.0
    score = 0.0
    if len(response) >= 20:
        score += 0.3
    elif len(response) >= 5:
        score += 0.1
    if 50 <= len(response) <= 2000:
        score += 0.3
    elif len(response) > 2000:
        score += 0.1
    if len(response.split()) >= 5:
        score += 0.2
    qw = set(query.lower().split())
    rw = set(response.lower().split())
    if qw & rw:
        score += 0.2
    return min(1.0, score)

# ─── MINER ───────────────────────────────────────────────────

class SimMiner:
    def __init__(self, wallet: dict, use_api: bool = False,
                 client: Optional[object] = None, model: str = ""):
        self.wallet     = wallet
        self.use_api    = use_api
        self.client     = client
        self.model      = model
        self.personality = random.choice(PERSONALITIES)
        self.latencies: List[float] = []
        self.ok = 0
        self.err = 0

    def _fallback(self, message: str) -> str:
        resp = random.choice(FALLBACK_RESPONSES)
        # add tiny variation per miner uid
        suffix = "" if self.wallet["uid"] % 3 != 0 else " Let me know if you want to go deeper!"
        return resp + suffix

    async def respond(self, message: str) -> Tuple[str, float]:
        t0 = time.monotonic()
        if self.use_api and self.client and HAS_OPENAI:
            try:
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.personality},
                        {"role": "user",   "content": message},
                    ],
                    max_tokens=300,
                    temperature=0.7,
                    timeout=25.0,
                )
                text = completion.choices[0].message.content
                self.ok += 1
                lat = (time.monotonic() - t0) * 1000
                self.latencies.append(lat)
                return text, lat
            except Exception as e:
                self.err += 1

        # Simulate network latency for fallback
        await asyncio.sleep(random.uniform(0.05, 0.3))
        text = self._fallback(message)
        self.ok += 1
        lat = (time.monotonic() - t0) * 1000
        self.latencies.append(lat)
        return text, lat

# ─── VALIDATOR ───────────────────────────────────────────────

class SimValidator:
    def __init__(self, wallet: dict, miners: List[SimMiner],
                 use_api_judge: bool = False,
                 judge_client: Optional[object] = None,
                 judge_model: str = "anthropic/claude-3.5-haiku",
                 sample_size: int = SAMPLE_SIZE):
        self.wallet        = wallet
        self.miners        = miners
        self.use_api_judge = use_api_judge
        self.judge_client  = judge_client
        self.judge_model   = judge_model
        self.sample_size   = min(sample_size, len(miners))
        self.scores        = [0.0] * len(miners)   # one score per miner uid
        self.round_logs: List[dict] = []
        self.judge_ok  = 0
        self.judge_err = 0

    async def _judge(self, query: str, response: str) -> float:
        if self.use_api_judge and self.judge_client and HAS_OPENAI:
            try:
                completion = await self.judge_client.chat.completions.create(
                    model=self.judge_model,
                    messages=[{"role": "user", "content": JUDGE_PROMPT.format(
                        query=query, response=response
                    )}],
                    max_tokens=10,
                    temperature=0.0,
                    timeout=20.0,
                )
                raw = completion.choices[0].message.content.strip()
                s = max(0.0, min(1.0, float(raw)))
                self.judge_ok += 1
                return s
            except Exception:
                self.judge_err += 1
        return heuristic_score(query, response)

    async def run_round(self, round_num: int) -> dict:
        query    = random.choice(TEST_QUERIES)
        selected = random.sample(self.miners, self.sample_size)

        # Query miners concurrently
        resp_tasks = [m.respond(query) for m in selected]
        raw = await asyncio.gather(*resp_tasks, return_exceptions=True)

        responses: List[str] = []
        latencies: List[float] = []
        for r in raw:
            if isinstance(r, Exception):
                responses.append("")
                latencies.append(0.0)
            else:
                responses.append(r[0])
                latencies.append(r[1])

        # Score concurrently
        score_tasks = [self._judge(query, r) for r in responses]
        raw_scores  = await asyncio.gather(*score_tasks, return_exceptions=True)
        round_scores = [
            (s if isinstance(s, float) else 0.0) for s in raw_scores
        ]

        # Update moving averages
        for i, miner in enumerate(selected):
            uid = miner.wallet["uid"]
            self.scores[uid] = (
                MOVING_ALPHA * round_scores[i]
                + (1 - MOVING_ALPHA) * self.scores[uid]
            )

        log = {
            "validator": self.wallet["name"],
            "round": round_num,
            "query": query[:60],
            "num_queried": len(selected),
            "avg_score": statistics.mean(round_scores) if round_scores else 0.0,
            "min_score": min(round_scores) if round_scores else 0.0,
            "max_score": max(round_scores) if round_scores else 0.0,
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0.0,
        }
        self.round_logs.append(log)
        return log

    def weights(self) -> List[float]:
        total = sum(self.scores)
        if total == 0:
            return [0.0] * len(self.scores)
        return [s / total for s in self.scores]

# ─── PHASE 2 ─────────────────────────────────────────────────

async def phase2(validators: List[SimValidator], num_rounds: int, batch_size: int = 5):
    print(f"\n{'='*62}")
    print(f"📊  PHASE 2 — Response Generation + LLM-as-Judge Scoring")
    print(f"{'='*62}")
    total_planned = len(validators) * num_rounds * validators[0].sample_size
    print(f"    {len(validators)} validators × {num_rounds} rounds × "
          f"{validators[0].sample_size} miners/round = {total_planned} total queries\n")

    all_logs = []
    t_phase  = time.monotonic()

    for rnd in range(num_rounds):
        t_round = time.monotonic()
        print(f"  🔄  Round {rnd+1}/{num_rounds} ...", flush=True)
        round_logs = []

        for i in range(0, len(validators), batch_size):
            batch   = validators[i : i + batch_size]
            results = await asyncio.gather(
                *[v.run_round(rnd) for v in batch], return_exceptions=True
            )
            for r in results:
                if isinstance(r, dict):
                    round_logs.append(r)

        all_logs.extend(round_logs)

        if round_logs:
            avg_s = statistics.mean(r["avg_score"] for r in round_logs)
            avg_l = statistics.mean(r["avg_latency_ms"] for r in round_logs)
            elapsed = time.monotonic() - t_round
            print(f"       avg_score={avg_s:.4f}  avg_latency={avg_l:.0f}ms  "
                  f"time={elapsed:.1f}s")

    phase_time = time.monotonic() - t_phase
    total_q    = sum(v.judge_ok + v.judge_err + v.sample_size
                     for v in validators)
    judge_ok   = sum(v.judge_ok  for v in validators)
    judge_err  = sum(v.judge_err for v in validators)
    all_scores = [r["avg_score"] for r in all_logs]

    def _std(xs):
        if len(xs) < 2: return 0.0
        m = statistics.mean(xs)
        return math.sqrt(sum((x - m)**2 for x in xs) / len(xs))

    print(f"\n  📊  Phase 2 Summary")
    print(f"      Total queries:   {sum(len(v.round_logs) * v.sample_size for v in validators)}")
    print(f"      API judge calls: {judge_ok} ok / {judge_err} err")
    print(f"      Avg score:       {statistics.mean(all_scores):.4f}")
    print(f"      Std dev:         {_std(all_scores):.4f}")
    print(f"      Score range:     [{min(all_scores):.4f}, {max(all_scores):.4f}]")
    print(f"      Total time:      {phase_time:.1f}s")
    print(f"      Throughput:      "
          f"{len(all_logs) * validators[0].sample_size / phase_time:.1f} queries/s")

    return {
        "avg_score": statistics.mean(all_scores),
        "std_score": _std(all_scores),
        "min_score": min(all_scores),
        "max_score": max(all_scores),
        "judge_ok":  judge_ok,
        "judge_err": judge_err,
        "total_time_s": phase_time,
    }

# ─── PHASE 3 ─────────────────────────────────────────────────

def gini(weights: List[float]) -> float:
    if not weights or sum(weights) == 0:
        return 0.0
    ws = sorted(weights)
    n  = len(ws)
    idx = list(range(1, n + 1))
    return (sum((2 * i - n - 1) * w for i, w in zip(idx, ws))
            / (n * sum(ws)))

def pearson(a: List[float], b: List[float]) -> float:
    n = len(a)
    if n < 2: return 0.0
    ma, mb = sum(a)/n, sum(b)/n
    num = sum((x - ma)*(y - mb) for x, y in zip(a, b))
    da  = math.sqrt(sum((x - ma)**2 for x in a))
    db  = math.sqrt(sum((y - mb)**2 for y in b))
    if da == 0 or db == 0: return 0.0
    return num / (da * db)

async def phase3(validators: List[SimValidator], miners: List[SimMiner]):
    print(f"\n{'='*62}")
    print(f"⚖️   PHASE 3 — Weight Calculation + Consensus")
    print(f"{'='*62}")
    t_phase = time.monotonic()

    all_weights = [v.weights() for v in validators]

    # Consensus = mean across validators
    n_m = len(miners)
    consensus = [
        sum(all_weights[vi][mi] for vi in range(len(validators))) / len(validators)
        for mi in range(n_m)
    ]
    total = sum(consensus)
    if total > 0:
        consensus = [w / total for w in consensus]

    # Top 20
    top20 = sorted(range(n_m), key=lambda i: consensus[i], reverse=True)[:20]
    print(f"\n  🏆  Top 20 miners by consensus weight:")
    for rank, uid in enumerate(top20):
        if consensus[uid] <= 0:
            break
        mode = "API" if miners[uid].use_api else "fallback"
        lat  = (statistics.mean(miners[uid].latencies)
                if miners[uid].latencies else 0)
        print(f"      #{rank+1:2d}  UID {uid:4d}  weight={consensus[uid]:.6f}"
              f"  mode={mode}  avg_lat={lat:.0f}ms")

    # Gini
    g = gini(consensus)

    # Validator agreement (pairwise Pearson on their weight vectors)
    agreements = []
    for i in range(len(validators)):
        for j in range(i + 1, len(validators)):
            r = pearson(all_weights[i], all_weights[j])
            if not math.isnan(r):
                agreements.append(r)
    avg_agree = statistics.mean(agreements) if agreements else 0.0

    # Miners with non-zero weight
    active = sum(1 for w in consensus if w > 0)

    phase_time = time.monotonic() - t_phase

    print(f"\n  📊  Phase 3 Summary")
    print(f"      Miners with weight:    {active} / {n_m}")
    print(f"      Gini coefficient:      {g:.4f}  (0=equal, 1=winner-take-all)")
    print(f"      Validator agreement:   {avg_agree:.4f}  (1=perfect consensus)")
    print(f"      Total time:            {phase_time:.3f}s")

    return {
        "active_miners": active,
        "gini": g,
        "validator_agreement": avg_agree,
        "total_time_s": phase_time,
    }

# ─── MINER PERF SUMMARY ──────────────────────────────────────

def miner_summary(miners: List[SimMiner]):
    print(f"\n{'='*62}")
    print(f"🤖  MINER PERFORMANCE")
    print(f"{'='*62}")
    api_m  = [m for m in miners if m.use_api]
    fall_m = [m for m in miners if not m.use_api]

    def _stat(group, label):
        all_lats = [l for m in group for l in m.latencies]
        ok  = sum(m.ok  for m in group)
        err = sum(m.err for m in group)
        print(f"  {label} ({len(group)} miners):")
        if all_lats:
            all_lats_s = sorted(all_lats)
            p95 = all_lats_s[int(len(all_lats_s) * 0.95)]
            print(f"    Avg latency:  {statistics.mean(all_lats):.0f}ms")
            print(f"    P95 latency:  {p95:.0f}ms")
        rate = f"{100*ok/(ok+err):.1f}%" if ok + err > 0 else "n/a"
        print(f"    Success rate: {ok}/{ok+err} ({rate})")

    if api_m:  _stat(api_m,  "API-backed ")
    if fall_m: _stat(fall_m, "Fallback   ")

# ─── PROTOCOL SANITY CHECK ───────────────────────────────────

def protocol_sanity(n: int = 2000):
    print(f"\n{'='*62}")
    print(f"📦  PROTOCOL SANITY — {n} simulated CompanionRequests")
    print(f"{'='*62}")
    t0 = time.monotonic()
    reqs = []
    for i in range(n):
        req = {
            "message": random.choice(TEST_QUERIES),
            "user_id": f"user_{i:05d}",
            "conversation_history": [
                {"role": "user",      "content": f"msg {j}"}
                for j in range(random.randint(0, 6))
            ],
            "response":    None,
            "confidence":  None,
        }
        req["response"]   = random.choice(FALLBACK_RESPONSES)
        req["confidence"] = round(random.uniform(0.5, 1.0), 3)
        reqs.append(req)
    elapsed = time.monotonic() - t0
    serial = json.dumps(reqs)
    back   = json.loads(serial)
    print(f"  Created & serialized {n} requests in {elapsed*1000:.0f}ms")
    print(f"  Payload size: {len(serial)/1024:.1f} KB")
    print(f"  Throughput:   {n/elapsed:.0f} req/s")
    assert len(back) == n, "round-trip mismatch!"
    print(f"  Round-trip:   ✅ OK")

# ─── MAIN ────────────────────────────────────────────────────

async def main(args):
    print(f"\n{'='*62}")
    print(f"🚀  PROJECT NOBI — STRESS TEST")
    print(f"{'='*62}")
    print(f"  Miners:      {args.miners}")
    print(f"  Validators:  {args.validators}")
    print(f"  Rounds:      {args.rounds}")
    print(f"  Sample size: {args.sample_size}")
    print(f"  LLM judge:   {'OpenRouter ✅' if args.api_key and HAS_OPENAI else '❌ heuristic'}")
    print(f"  Started:     {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # Protocol sanity
    protocol_sanity(2000)

    # Build judge client
    judge_client = None
    use_api_judge = False
    if args.api_key and HAS_OPENAI:
        judge_client  = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=args.api_key,
        )
        use_api_judge = True

    # Build miner API client (same key, different base)
    miner_client = judge_client  # reuse

    # Create wallets
    print(f"\n🔧  Generating {args.miners} miner wallets + {args.validators} validator wallets...")
    miner_wallets = [make_wallet("nobi-miner", i)     for i in range(args.miners)]
    val_wallets   = [make_wallet("nobi-val",   i)     for i in range(args.validators)]

    # Create miners — 20% API-backed (only if client available)
    models = [
        "anthropic/claude-3.5-haiku",
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct",
    ]
    miners = []
    for w in miner_wallets:
        use_api = (w["uid"] % 5 == 0) and use_api_judge
        miners.append(SimMiner(
            wallet   = w,
            use_api  = use_api,
            client   = miner_client if use_api else None,
            model    = random.choice(models) if use_api else "",
        ))
    api_count = sum(1 for m in miners if m.use_api)
    print(f"  ✅ {len(miners)} miners  ({api_count} API-backed, "
          f"{len(miners)-api_count} heuristic fallback)")

    # Create validators
    validators = [
        SimValidator(
            wallet        = w,
            miners        = miners,
            use_api_judge = use_api_judge,
            judge_client  = judge_client,
            judge_model   = "anthropic/claude-3.5-haiku",
            sample_size   = args.sample_size,
        )
        for w in val_wallets
    ]
    print(f"  ✅ {len(validators)} validators")

    t_total = time.monotonic()

    # Run phases
    p2_stats = {}
    p3_stats = {}

    if args.phase in ("2", "full"):
        p2_stats = await phase2(validators, args.rounds)

    if args.phase in ("3", "full"):
        p3_stats = await phase3(validators, miners)

    miner_summary(miners)

    total_time = time.monotonic() - t_total
    print(f"\n{'='*62}")
    print(f"✅  COMPLETE — {total_time:.1f}s total")
    print(f"{'='*62}")

    # Save JSON report
    os.makedirs(args.output, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(args.output, f"stress_{ts}.json")
    report = {
        "timestamp": ts,
        "config": {
            "miners": args.miners, "validators": args.validators,
            "rounds": args.rounds, "sample_size": args.sample_size,
        },
        "phase2": p2_stats,
        "phase3": p3_stats,
        "total_time_s": total_time,
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  📄  Report → {report_path}")

def parse_args():
    p = argparse.ArgumentParser(description="Project Nobi Stress Test")
    p.add_argument("--miners",       type=int, default=NUM_MINERS)
    p.add_argument("--validators",   type=int, default=NUM_VALIDATORS)
    p.add_argument("--rounds",       type=int, default=NUM_ROUNDS)
    p.add_argument("--sample-size",  type=int, default=SAMPLE_SIZE)
    p.add_argument("--phase", choices=["2", "3", "full"], default="full")
    p.add_argument("--api-key",  type=str, default="")
    p.add_argument("--output",   type=str, default="/root/project-nobi/stress_results")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    # pick up key from env if not passed
    if not args.api_key:
        args.api_key = os.environ.get("OPENROUTER_API_KEY", "")
    asyncio.run(main(args))
