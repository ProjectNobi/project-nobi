"""
Test: stress_test_10k — import validation + mini run (100 users).

These tests verify the stress test suite itself:
  1. Module imports cleanly
  2. All scenario functions are callable
  3. Mini run (100 users) completes successfully
  4. Report is generated
  5. All pass/fail criteria match expected structure
"""

import os
import sys
import asyncio
import tempfile
import json
import pytest

# Add project root to path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

# Ensure env vars set before importing stress test (avoids heavy model loads)
# NOTE: set at module level so the stress test module imports without loading heavy models,
# but we restore them in the autouse fixture so other test modules are not affected.
os.environ["NOBI_DISABLE_LLM_EXTRACTOR"] = "1"
os.environ["NOBI_DISABLE_EMBEDDINGS"] = "1"


@pytest.fixture(autouse=True, scope="module")
def _restore_env_after_stress_tests():
    """Restore env vars after this module's tests so they don't affect other test files."""
    yield
    os.environ.pop("NOBI_DISABLE_EMBEDDINGS", None)
    os.environ.pop("NOBI_DISABLE_LLM_EXTRACTOR", None)


# ─── Import tests ─────────────────────────────────────────────

def test_stress_module_imports():
    """Stress test module must import cleanly."""
    from scripts import stress_test_10k as st
    assert hasattr(st, "run_all"), "run_all must exist"
    assert hasattr(st, "MINI_CONFIG"), "MINI_CONFIG must exist"
    assert hasattr(st, "FULL_CONFIG"), "FULL_CONFIG must exist"
    assert hasattr(st, "BENCHMARKS"), "BENCHMARKS must exist"


def test_stress_config_structure():
    """MINI_CONFIG and FULL_CONFIG must have all required keys."""
    from scripts import stress_test_10k as st

    required_keys = [
        "chat_users", "chat_batch_size",
        "memory_users", "memories_per_user",
        "crypto_ops", "crypto_miners",
        "rate_users", "rate_msgs_per_user",
        "graph_memories", "graph_users",
        "scoring_miners",
        "pipeline_users",
    ]

    for key in required_keys:
        assert key in st.MINI_CONFIG, f"MINI_CONFIG missing key: {key}"
        assert key in st.FULL_CONFIG, f"FULL_CONFIG missing key: {key}"

    # Mini config should be smaller than full
    assert st.MINI_CONFIG["chat_users"] < st.FULL_CONFIG["chat_users"]
    assert st.MINI_CONFIG["memory_users"] < st.FULL_CONFIG["memory_users"]


def test_benchmark_keys():
    """BENCHMARKS must contain all 7 required criteria."""
    from scripts import stress_test_10k as st

    required = [
        "chat_success_rate_pct",
        "memory_store_p95_ms",
        "memory_recall_p95_ms",
        "encryption_throughput_ops",
        "rate_limiter_accuracy_pct",
        "scoring_256_total_s",
        "rss_growth_pct",
    ]
    for key in required:
        assert key in st.BENCHMARKS, f"BENCHMARKS missing: {key}"
        val, op = st.BENCHMARKS[key]
        assert op in (">=", "<="), f"Invalid operator for {key}: {op}"


def test_scenario_functions_exist():
    """All scenario runner functions must exist."""
    from scripts import stress_test_10k as st

    assert callable(st.run_scenario_a), "run_scenario_a must be callable"
    assert callable(st.run_scenario_b), "run_scenario_b must be callable"
    assert callable(st.run_scenario_c), "run_scenario_c must be callable"
    assert callable(st.run_scenario_d), "run_scenario_d must be callable"
    assert callable(st.run_scenario_e), "run_scenario_e must be callable"
    assert callable(st.run_scenario_f), "run_scenario_f must be callable"
    assert callable(st.run_scenario_g), "run_scenario_g must be callable"


def test_utility_functions():
    """Utility functions must work correctly."""
    from scripts.stress_test_10k import percentile, make_user_id, ScenarioResult

    # percentile
    data = list(range(100))
    assert percentile(data, 50) == 49.5
    assert percentile(data, 95) == pytest.approx(94.05, abs=0.1)
    assert percentile([], 50) == 0.0

    # make_user_id
    uid = make_user_id(42)
    assert uid == "stress_user_000042"
    assert uid.startswith("stress_user_")

    # ScenarioResult
    r = ScenarioResult("test")
    assert r.passed is True
    r.fail("test failure")
    assert r.passed is False
    assert "test failure" in r.failures


def test_rate_limiter():
    """Token bucket rate limiter must accept and reject correctly."""
    from scripts.stress_test_10k import TokenBucketRateLimiter

    # Burst of 5, rate=10/60 req/sec
    limiter = TokenBucketRateLimiter(rate=10/60, burst=5)
    uid = "test_user_001"

    # First 5 requests should be accepted (burst)
    accepts = 0
    for i in range(5):
        if limiter.allow(uid, now=0.0):
            accepts += 1
    assert accepts == 5, f"Expected 5 accepts in burst, got {accepts}"

    # 6th request immediately should be rejected (bucket empty)
    assert limiter.allow(uid, now=0.0) is False, "6th immediate request should be rejected"

    # After 12 seconds (2 tokens refilled), should accept again
    assert limiter.allow(uid, now=12.0) is True, "Should accept after 12s"


# ─── Mini run tests ────────────────────────────────────────────

def _run_async(coro):
    """Helper to run a coroutine synchronously."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.mark.timeout(120)
def test_scenario_a_mini():
    """Scenario A: 100 users, must complete with > 99% success rate."""
    from scripts.stress_test_10k import run_scenario_a, MINI_CONFIG

    cfg = dict(MINI_CONFIG)
    cfg["chat_users"] = 100
    cfg["chat_batch_size"] = 25

    result = _run_async(run_scenario_a(cfg))
    assert result is not None
    assert result.metrics.get("total_users") == 100
    assert result.metrics.get("success_rate_pct", 0) >= 99.0, \
        f"Success rate too low: {result.metrics.get('success_rate_pct')}"


@pytest.mark.timeout(120)
def test_scenario_b_mini():
    """Scenario B: 10 users × 5 memories each."""
    from scripts.stress_test_10k import run_scenario_b

    cfg = {
        "memory_users": 10,
        "memories_per_user": 5,
    }
    result = _run_async(run_scenario_b(cfg))
    assert result is not None
    assert result.metrics.get("total_users") == 10
    assert result.metrics.get("total_stored", 0) > 0


@pytest.mark.timeout(60)
def test_scenario_c_mini():
    """Scenario C: 50 crypto ops, should achieve > 100 ops/sec."""
    from scripts.stress_test_10k import run_scenario_c

    cfg = {
        "crypto_ops": 50,
        "crypto_miners": 16,
    }
    result = _run_async(run_scenario_c(cfg))
    assert result is not None
    # Throughput should be well above minimum (even on slow machines)
    throughput = result.metrics.get("aes_throughput_ops_sec", 0)
    assert throughput > 100, f"AES throughput too low: {throughput}"


@pytest.mark.timeout(30)
def test_scenario_d_mini():
    """Scenario D: Rate limiter accuracy > 99.9%."""
    from scripts.stress_test_10k import run_scenario_d

    cfg = {
        "rate_users": 20,
        "rate_msgs_per_user": 5,
    }
    result = _run_async(run_scenario_d(cfg))
    assert result is not None
    accuracy = result.metrics.get("accuracy_pct", 0)
    assert accuracy >= 99.9, f"Rate limiter accuracy too low: {accuracy}"


@pytest.mark.timeout(60)
def test_scenario_e_mini():
    """Scenario E: Memory graph growth — 500 memories, no memory leak."""
    from scripts.stress_test_10k import run_scenario_e

    cfg = {
        "graph_memories": 500,
        "graph_users": 50,
    }
    result = _run_async(run_scenario_e(cfg))
    assert result is not None
    # RSS growth should be bounded (< 50% for small test)
    rss_growth = result.metrics.get("rss_growth_pct", 0)
    assert rss_growth < 50, f"RSS growth too high: {rss_growth}%"


@pytest.mark.timeout(30)
def test_scenario_f_mini():
    """Scenario F: Scoring 32 miners in < 5 seconds."""
    from scripts.stress_test_10k import run_scenario_f

    cfg = {"scoring_miners": 32}
    result = _run_async(run_scenario_f(cfg))
    assert result is not None
    duration = result.metrics.get("total_duration_s", 999)
    assert duration < 5.0, f"Scoring took too long: {duration}s"


@pytest.mark.timeout(120)
def test_scenario_g_mini():
    """Scenario G: 20 users through full pipeline."""
    from scripts.stress_test_10k import run_scenario_g

    cfg = {"pipeline_users": 20}
    result = _run_async(run_scenario_g(cfg))
    assert result is not None
    assert result.metrics.get("pipeline_runs", 0) > 0


@pytest.mark.timeout(300)
def test_full_mini_run():
    """Run all scenarios in mini mode — 100 users."""
    import argparse
    from scripts.stress_test_10k import run_all

    args = argparse.Namespace(
        mini=True,
        scenario="A,B,C,D,E,F,G",
        report=None,
    )

    # Use temp file for report
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
        tmp_report = f.name

    args.report = tmp_report

    try:
        results = _run_async(run_all(args))

        assert results is not None
        assert len(results) == 7, f"Expected 7 scenario results, got {len(results)}"

        # Check all scenarios ran
        names = [r.name for r in results]
        assert any("Chat" in n for n in names), "Scenario A missing"
        assert any("Memory System" in n for n in names), "Scenario B missing"
        assert any("Encryption" in n for n in names), "Scenario C missing"
        assert any("Rate" in n for n in names), "Scenario D missing"
        assert any("Graph" in n for n in names), "Scenario E missing"
        assert any("Scoring" in n for n in names), "Scenario F missing"
        assert any("Pipeline" in n for n in names), "Scenario G missing"

        # Report file should exist
        assert os.path.exists(tmp_report), "Report file not created"
        with open(tmp_report) as f:
            report_text = f.read()
        assert "PROJECT NOBI" in report_text
        assert "BENCHMARKS" in report_text

        # JSON report should also exist
        json_path = tmp_report.replace(".md", ".json")
        assert os.path.exists(json_path), "JSON report not created"
        with open(json_path) as f:
            json_report = json.load(f)
        assert "results" in json_report
        assert len(json_report["results"]) == 7

    finally:
        for path in [tmp_report, tmp_report.replace(".md", ".json")]:
            if os.path.exists(path):
                os.unlink(path)


# ─── Benchmark criteria tests ─────────────────────────────────

def test_benchmark_values_are_sane():
    """Benchmark thresholds should be within expected ranges."""
    from scripts.stress_test_10k import BENCHMARKS

    chat_rate, _ = BENCHMARKS["chat_success_rate_pct"]
    assert 95 <= chat_rate <= 100, f"Chat success rate benchmark seems off: {chat_rate}"

    store_p95, _ = BENCHMARKS["memory_store_p95_ms"]
    assert 1 <= store_p95 <= 1000, f"Store p95 benchmark seems off: {store_p95}"

    enc_throughput, _ = BENCHMARKS["encryption_throughput_ops"]
    assert 100 <= enc_throughput <= 1_000_000, f"Enc throughput benchmark seems off: {enc_throughput}"

    scoring_time, _ = BENCHMARKS["scoring_256_total_s"]
    assert 0.1 <= scoring_time <= 60, f"Scoring time benchmark seems off: {scoring_time}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--timeout=300", "-x"])
