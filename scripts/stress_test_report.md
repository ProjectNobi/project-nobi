═══════════════════════════════════════════════════════════════
  PROJECT NOBI — 10K STRESS TEST REPORT
  Date: 2026-03-23  Time: 16:29 UTC
  Mode: FULL (10K-user)
═══════════════════════════════════════════════════════════════

A. CONCURRENT CHAT LOAD (10,000 users)
  Status:  ✅ PASS
  Total Users: 10000
  Success Count: 9994
  Error Count: 6
  Success Rate Pct: 99.94
  P50 Latency Ms: 102.8
  P95 Latency Ms: 190.7
  P99 Latency Ms: 198.7
  Error Types: {'timeout': 6}
  Throughput Rps: 4366.6
  Duration S: 2.29
  Duration: 2.29s

B. MEMORY SYSTEM UNDER LOAD (10,000 users × 75 memories)
  Status:  ✅ PASS
  Total Users: 10000
  Memories Per User: 75
  Total Stored: 750000
  Total Recall Ops: 50000
  Store Rate Ops Sec: 585.4
  Recall Rate Ops Sec: 39.0
  Store P50 Ms: 6.44
  Store P95 Ms: 20.5
  Recall P50 Ms: 42.5
  Recall P95 Ms: 75.94
  Lock Contention Pct: 0.0
  Worker Errors: 0
  Duration S: 1281.16
  Duration: 1281.16s

C. ENCRYPTION UNDER LOAD (1,000 AES ops + 256 HPKE miners)
  Status:  ✅ PASS
  Aes Gcm Ops: 2000
  Aes Throughput Ops Sec: 4525.0
  Aes Enc P50 Us: 1400.2
  Aes Enc P95 Us: 3800.0
  Aes Dec P50 Us: 1325.5
  Aes Dec P95 Us: 3958.2
  Fernet Ops: 1000
  Fernet P50 Ms: 32.73
  Fernet P95 Ms: 45.37
  Hpke Miners: 256
  Hpke P50 Ms: 0.31
  Hpke P95 Ms: 0.38
  Duration S: 35.06
  Duration: 35.06s

D. RATE LIMITING UNDER LOAD (100 users × 20 msgs)
  Status:  ✅ PASS
  Total Requests: 2000
  Accepts: 1344
  Rejects: 656
  Reject Rate Pct: 32.8
  False Positives: 0
  False Negatives: 0
  Accuracy Pct: 100.0
  Duration S: 0.004
  Duration: 0.00s

E. MEMORY GRAPH GROWTH (100,000 memories)
  Status:  ✅ PASS
  Total Memories: 100000
  Total Users: 10000
  Insert Rate Ops Sec: 101705.0
  Insert P50 Ms: 0.001
  Insert P95 Ms: 0.001
  Query P50 Ms: 0.15
  Query P95 Ms: 0.19
  Query Trend: stable
  Rss Start Mb: 199.7
  Rss End Mb: 219.1
  Rss Growth Pct: 9.8
  Checkpoints: 20
  Duration S: 0.98
  Duration: 0.98s

F. VALIDATOR SCORING AT 256 SCALE
  Status:  ✅ PASS
  Miners: 256
  Rounds: 5
  Total Scored: 1280
  Scoring Throughput Miners Sec: 2280.2
  Round P50 Ms: 109.9
  Round P95 Ms: 119.2
  Weight Calc P50 Ms: 0.04
  Total Duration S: 0.561
  Duration: 0.56s

G. FULL PIPELINE INTEGRATION (1,000 users)
  Status:  ✅ PASS
  Users: 1000
  Pipeline Runs: 5467
  Errors: 0
  E2E P50 Ms: 74.2
  E2E P95 Ms: 226.6
  E2E P99 Ms: 434.6
  Store P50 Ms: 27.2
  Recall P50 Ms: 18.6
  Respond P50 Ms: 6.9
  Score P50 Ms: 0.02
  Pipeline Throughput: 86.5
  Duration S: 63.21
  Duration: 63.21s

═══════════════════════════════════════════════════════════════
  PERFORMANCE BENCHMARKS
═══════════════════════════════════════════════════════════════

  Chat success rate
    Required: >= 99%
    Actual:   99.94
    Result:   ✅ PASS

  Memory store p95 (load)
    Required: <= 150ms
    Actual:   20.5
    Result:   ✅ PASS

  Memory recall p95 (load)
    Required: <= 150ms
    Actual:   75.94
    Result:   ✅ PASS

  Encryption throughput
    Required: >= 1000/sec
    Actual:   4525.0
    Result:   ✅ PASS

  Rate limiter accuracy
    Required: >= 99.9%
    Actual:   100.0
    Result:   ✅ PASS

  256-miner scoring time
    Required: <= 5s
    Actual:   0.56
    Result:   ✅ PASS

  RSS memory growth
    Required: <= 10%
    Actual:   9.8
    Result:   ✅ PASS

═══════════════════════════════════════════════════════════════
  OVERALL SUMMARY
═══════════════════════════════════════════════════════════════

  Scenarios:   7/7 passed
  Benchmarks:  7/7 passed
  Total time:  1383.8s

  Verdict:     🟢 MAINNET READY

═══════════════════════════════════════════════════════════════