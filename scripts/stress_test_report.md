═══════════════════════════════════════════════════════════════
  PROJECT NOBI — 10K STRESS TEST REPORT
  Date: 2026-03-23  Time: 15:25 UTC
  Mode: FULL (10K-user)
═══════════════════════════════════════════════════════════════

A. CONCURRENT CHAT LOAD (10,000 users)
  Status:  ✅ PASS
  Total Users: 10000
  Success Count: 9990
  Error Count: 10
  Success Rate Pct: 99.9
  P50 Latency Ms: 103.6
  P95 Latency Ms: 190.2
  P99 Latency Ms: 198.1
  Error Types: {'timeout': 10}
  Throughput Rps: 4411.6
  Duration S: 2.27
  Duration: 2.27s

B. MEMORY SYSTEM UNDER LOAD (10,000 users × 75 memories)
  Status:  ✅ PASS
  Total Users: 10000
  Memories Per User: 75
  Total Stored: 750000
  Total Recall Ops: 50000
  Store Rate Ops Sec: 687.1
  Recall Rate Ops Sec: 45.8
  Store P50 Ms: 6.0
  Store P95 Ms: 18.69
  Recall P50 Ms: 41.4
  Recall P95 Ms: 71.31
  Lock Contention Pct: 0.0
  Worker Errors: 0
  Duration S: 1091.54
  Duration: 1091.54s

C. ENCRYPTION UNDER LOAD (1,000 AES ops + 256 HPKE miners)
  Status:  ✅ PASS
  Aes Gcm Ops: 2000
  Aes Throughput Ops Sec: 4632.0
  Aes Enc P50 Us: 1406.1
  Aes Enc P95 Us: 3724.4
  Aes Dec P50 Us: 1283.8
  Aes Dec P95 Us: 3896.3
  Fernet Ops: 1000
  Fernet P50 Ms: 32.06
  Fernet P95 Ms: 35.1
  Hpke Miners: 256
  Hpke P50 Ms: 0.3
  Hpke P95 Ms: 0.36
  Duration S: 33.25
  Duration: 33.25s

D. RATE LIMITING UNDER LOAD (100 users × 20 msgs)
  Status:  ✅ PASS
  Total Requests: 2000
  Accepts: 1330
  Rejects: 670
  Reject Rate Pct: 33.5
  False Positives: 0
  False Negatives: 0
  Accuracy Pct: 100.0
  Duration S: 0.006
  Duration: 0.01s

E. MEMORY GRAPH GROWTH (100,000 memories)
  Status:  ✅ PASS
  Total Memories: 100000
  Total Users: 10000
  Insert Rate Ops Sec: 102107.0
  Insert P50 Ms: 0.001
  Insert P95 Ms: 0.001
  Query P50 Ms: 0.16
  Query P95 Ms: 0.2
  Query Trend: stable
  Rss Start Mb: 194.6
  Rss End Mb: 211.9
  Rss Growth Pct: 8.9
  Checkpoints: 20
  Duration S: 0.98
  Duration: 0.98s

F. VALIDATOR SCORING AT 256 SCALE
  Status:  ✅ PASS
  Miners: 256
  Rounds: 5
  Total Scored: 1280
  Scoring Throughput Miners Sec: 2321.9
  Round P50 Ms: 107.5
  Round P95 Ms: 118.4
  Weight Calc P50 Ms: 0.04
  Total Duration S: 0.551
  Duration: 0.55s

G. FULL PIPELINE INTEGRATION (1,000 users)
  Status:  ✅ PASS
  Users: 1000
  Pipeline Runs: 5457
  Errors: 0
  E2E P50 Ms: 75.0
  E2E P95 Ms: 222.8
  E2E P99 Ms: 412.3
  Store P50 Ms: 28.3
  Recall P50 Ms: 18.6
  Respond P50 Ms: 6.6
  Score P50 Ms: 0.02
  Pipeline Throughput: 86.6
  Duration S: 63.0
  Duration: 63.00s

═══════════════════════════════════════════════════════════════
  PERFORMANCE BENCHMARKS
═══════════════════════════════════════════════════════════════

  Chat success rate
    Required: >= 99%
    Actual:   99.9
    Result:   ✅ PASS

  Memory store p95 (load)
    Required: <= 150ms
    Actual:   18.69
    Result:   ✅ PASS

  Memory recall p95 (load)
    Required: <= 150ms
    Actual:   71.31
    Result:   ✅ PASS

  Encryption throughput
    Required: >= 1000/sec
    Actual:   4632.0
    Result:   ✅ PASS

  Rate limiter accuracy
    Required: >= 99.9%
    Actual:   100.0
    Result:   ✅ PASS

  256-miner scoring time
    Required: <= 5s
    Actual:   0.55
    Result:   ✅ PASS

  RSS memory growth
    Required: <= 10%
    Actual:   8.9
    Result:   ✅ PASS

═══════════════════════════════════════════════════════════════
  OVERALL SUMMARY
═══════════════════════════════════════════════════════════════

  Scenarios:   7/7 passed
  Benchmarks:  7/7 passed
  Total time:  1192.1s

  Verdict:     🟢 MAINNET READY

═══════════════════════════════════════════════════════════════