═══════════════════════════════════════════════════════════════
  PROJECT NOBI — 10K STRESS TEST REPORT
  Date: 2026-03-23  Time: 14:28 UTC
  Mode: MINI (100-user)
═══════════════════════════════════════════════════════════════

A. CONCURRENT CHAT LOAD (100 users)
  Status:  ✅ PASS
  Total Users: 100
  Success Count: 100
  Error Count: 0
  Success Rate Pct: 100.0
  P50 Latency Ms: 79.1
  P95 Latency Ms: 191.5
  P99 Latency Ms: 198.9
  Error Types: {}
  Throughput Rps: 217.9
  Duration S: 0.46
  Duration: 0.46s

B. MEMORY SYSTEM UNDER LOAD (100 users × 10 memories)
  Status:  ✅ PASS
  Total Users: 100
  Memories Per User: 10
  Total Stored: 1000
  Total Recall Ops: 500
  Store Rate Ops Sec: 179.9
  Recall Rate Ops Sec: 90.0
  Store P50 Ms: 5.35
  Store P95 Ms: 29.1
  Recall P50 Ms: 15.1
  Recall P95 Ms: 55.07
  Lock Contention Pct: 0.0
  Worker Errors: 0
  Duration S: 5.56
  Duration: 5.56s

C. ENCRYPTION UNDER LOAD (100 AES ops + 32 HPKE miners)
  Status:  ✅ PASS
  Aes Gcm Ops: 192
  Aes Throughput Ops Sec: 4465.0
  Aes Enc P50 Us: 1245.4
  Aes Enc P95 Us: 3527.6
  Aes Dec P50 Us: 1003.5
  Aes Dec P95 Us: 3449.7
  Fernet Ops: 100
  Fernet P50 Ms: 32.3
  Fernet P95 Ms: 42.81
  Hpke Miners: 32
  Hpke P50 Ms: 0.42
  Hpke P95 Ms: 0.45
  Duration S: 3.4
  Duration: 3.40s

D. RATE LIMITING UNDER LOAD (20 users × 5 msgs)
  Status:  ✅ PASS
  Total Requests: 100
  Accepts: 100
  Rejects: 0
  Reject Rate Pct: 0.0
  False Positives: 0
  False Negatives: 0
  Accuracy Pct: 100.0
  Duration S: 0.0
  Duration: 0.00s

E. MEMORY GRAPH GROWTH (1,000 memories)
  Status:  ✅ PASS
  Total Memories: 1000
  Total Users: 100
  Insert Rate Ops Sec: 54302.0
  Insert P50 Ms: 0.001
  Insert P95 Ms: 0.001
  Query P50 Ms: 0.06
  Query P95 Ms: 0.1
  Query Trend: stable
  Rss Start Mb: 117.8
  Rss End Mb: 118.1
  Rss Growth Pct: 0.3
  Checkpoints: 20
  Duration S: 0.02
  Duration: 0.02s

F. VALIDATOR SCORING AT 32 SCALE
  Status:  ✅ PASS
  Miners: 32
  Rounds: 5
  Total Scored: 160
  Scoring Throughput Miners Sec: 12308.0
  Round P50 Ms: 2.6
  Round P95 Ms: 2.6
  Weight Calc P50 Ms: 0.0
  Total Duration S: 0.013
  Duration: 0.01s

G. FULL PIPELINE INTEGRATION (50 users)
  Status:  ✅ PASS
  Users: 50
  Pipeline Runs: 274
  Errors: 0
  E2E P50 Ms: 34.6
  E2E P95 Ms: 67.0
  E2E P99 Ms: 84.6
  Store P50 Ms: 12.5
  Recall P50 Ms: 13.5
  Respond P50 Ms: 5.7
  Score P50 Ms: 0.02
  Pipeline Throughput: 216.6
  Duration S: 1.27
  Duration: 1.27s

═══════════════════════════════════════════════════════════════
  PERFORMANCE BENCHMARKS
═══════════════════════════════════════════════════════════════

  Chat success rate
    Required: >= 99%
    Actual:   100.0
    Result:   ✅ PASS

  Memory store p95 (load)
    Required: <= 150ms
    Actual:   29.1
    Result:   ✅ PASS

  Memory recall p95 (load)
    Required: <= 150ms
    Actual:   55.07
    Result:   ✅ PASS

  Encryption throughput
    Required: >= 1000/sec
    Actual:   4465.0
    Result:   ✅ PASS

  Rate limiter accuracy
    Required: >= 99.9%
    Actual:   100.0
    Result:   ✅ PASS

  256-miner scoring time
    Required: <= 5s
    Actual:   0.01
    Result:   ✅ PASS

  RSS memory growth
    Required: <= 10%
    Actual:   0.3
    Result:   ✅ PASS

═══════════════════════════════════════════════════════════════
  OVERALL SUMMARY
═══════════════════════════════════════════════════════════════

  Scenarios:   7/7 passed
  Benchmarks:  7/7 passed
  Total time:  10.7s

  Verdict:     🟢 MAINNET READY

═══════════════════════════════════════════════════════════════