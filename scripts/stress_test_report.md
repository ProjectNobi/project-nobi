═══════════════════════════════════════════════════════════════
  PROJECT NOBI — 10K STRESS TEST REPORT
  Date: 2026-03-23  Time: 17:28 UTC
  Mode: FULL (10K-user)
═══════════════════════════════════════════════════════════════

A. CONCURRENT CHAT LOAD (10,000 users)
  Status:  ✅ PASS
  Total Users: 10000
  Success Count: 9992
  Error Count: 8
  Success Rate Pct: 99.92
  P50 Latency Ms: 102.3
  P95 Latency Ms: 191.4
  P99 Latency Ms: 198.8
  Error Types: {'timeout': 8}
  Throughput Rps: 4416.9
  Duration S: 2.26
  Duration: 2.26s

B. MEMORY SYSTEM UNDER LOAD (10,000 users × 75 memories)
  Status:  ✅ PASS
  Total Users: 10000
  Memories Per User: 75
  Total Stored: 750000
  Total Recall Ops: 50000
  Store Rate Ops Sec: 700.1
  Recall Rate Ops Sec: 46.7
  Store P50 Ms: 5.84
  Store P95 Ms: 18.07
  Recall P50 Ms: 42.01
  Recall P95 Ms: 70.74
  Lock Contention Pct: 0.0
  Worker Errors: 0
  Duration S: 1071.27
  Duration: 1071.27s

C. ENCRYPTION UNDER LOAD (1,000 AES ops + 256 HPKE miners)
  Status:  ✅ PASS
  Aes Gcm Ops: 2000
  Aes Throughput Ops Sec: 4812.0
  Aes Enc P50 Us: 1330.7
  Aes Enc P95 Us: 3719.2
  Aes Dec P50 Us: 1351.5
  Aes Dec P95 Us: 3503.1
  Fernet Ops: 1000
  Fernet P50 Ms: 31.99
  Fernet P95 Ms: 34.9
  Hpke Miners: 256
  Hpke P50 Ms: 0.3
  Hpke P95 Ms: 0.51
  Duration S: 32.97
  Duration: 32.97s

D. RATE LIMITING UNDER LOAD (100 users × 20 msgs)
  Status:  ✅ PASS
  Total Requests: 2000
  Accepts: 1333
  Rejects: 667
  Reject Rate Pct: 33.35
  False Positives: 0
  False Negatives: 0
  Accuracy Pct: 100.0
  Duration S: 0.004
  Duration: 0.00s

E. MEMORY GRAPH GROWTH (100,000 memories)
  Status:  ❌ FAIL
  Total Memories: 100000
  Total Users: 10000
  Insert Rate Ops Sec: 108331.0
  Insert P50 Ms: 0.001
  Insert P95 Ms: 0.001
  Query P50 Ms: 0.12
  Query P95 Ms: 0.15
  Query Trend: stable
  Rss Start Mb: 202.6
  Rss End Mb: 224.3
  Rss Growth Pct: 10.7
  Checkpoints: 20
  Duration S: 0.92
  ⚠️  FAILURE: RSS growth 10.7% > 10.0%
  Duration: 0.92s

F. VALIDATOR SCORING AT 256 SCALE
  Status:  ✅ PASS
  Miners: 256
  Rounds: 5
  Total Scored: 1280
  Scoring Throughput Miners Sec: 2196.1
  Round P50 Ms: 106.9
  Round P95 Ms: 143.8
  Weight Calc P50 Ms: 0.04
  Total Duration S: 0.583
  Duration: 0.58s

G. FULL PIPELINE INTEGRATION (1,000 users)
  Status:  ✅ PASS
  Users: 1000
  Pipeline Runs: 5576
  Errors: 0
  E2E P50 Ms: 73.1
  E2E P95 Ms: 219.8
  E2E P99 Ms: 422.3
  Store P50 Ms: 26.0
  Recall P50 Ms: 19.5
  Respond P50 Ms: 6.8
  Score P50 Ms: 0.02
  Pipeline Throughput: 88.4
  Duration S: 63.06
  Duration: 63.06s

═══════════════════════════════════════════════════════════════
  PERFORMANCE BENCHMARKS
═══════════════════════════════════════════════════════════════

  Chat success rate
    Required: >= 99%
    Actual:   99.92
    Result:   ✅ PASS

  Memory store p95 (load)
    Required: <= 150ms
    Actual:   18.07
    Result:   ✅ PASS

  Memory recall p95 (load)
    Required: <= 150ms
    Actual:   70.74
    Result:   ✅ PASS

  Encryption throughput
    Required: >= 1000/sec
    Actual:   4812.0
    Result:   ✅ PASS

  Rate limiter accuracy
    Required: >= 99.9%
    Actual:   100.0
    Result:   ✅ PASS

  256-miner scoring time
    Required: <= 5s
    Actual:   0.58
    Result:   ✅ PASS

  RSS memory growth
    Required: <= 10%
    Actual:   10.7
    Result:   ❌ FAIL

═══════════════════════════════════════════════════════════════
  OVERALL SUMMARY
═══════════════════════════════════════════════════════════════

  Scenarios:   6/7 passed
  Benchmarks:  6/7 passed
  Total time:  1171.6s

  Verdict:     🟡 PARTIAL PASS

═══════════════════════════════════════════════════════════════