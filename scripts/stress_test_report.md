═══════════════════════════════════════════════════════════════
  PROJECT NOBI — 10K STRESS TEST REPORT
  Date: 2026-03-23  Time: 16:21 UTC
  Mode: FULL (10K-user)
═══════════════════════════════════════════════════════════════

A. CONCURRENT CHAT LOAD (10,000 users)
  Status:  ✅ PASS
  Total Users: 10000
  Success Count: 9987
  Error Count: 13
  Success Rate Pct: 99.87
  P50 Latency Ms: 101.1
  P95 Latency Ms: 190.4
  P99 Latency Ms: 198.7
  Error Types: {'timeout': 13}
  Throughput Rps: 4455.1
  Duration S: 2.24
  Duration: 2.24s

B. MEMORY SYSTEM UNDER LOAD (10,000 users × 75 memories)
  Status:  ✅ PASS
  Total Users: 10000
  Memories Per User: 75
  Total Stored: 750000
  Total Recall Ops: 50000
  Store Rate Ops Sec: 651.0
  Recall Rate Ops Sec: 43.4
  Store P50 Ms: 6.57
  Store P95 Ms: 20.64
  Recall P50 Ms: 41.24
  Recall P95 Ms: 75.02
  Lock Contention Pct: 0.0
  Worker Errors: 0
  Duration S: 1152.01
  Duration: 1152.01s

C. ENCRYPTION UNDER LOAD (1,000 AES ops + 256 HPKE miners)
  Status:  ✅ PASS
  Aes Gcm Ops: 2000
  Aes Throughput Ops Sec: 5512.0
  Aes Enc P50 Us: 745.7
  Aes Enc P95 Us: 4160.6
  Aes Dec P50 Us: 597.1
  Aes Dec P95 Us: 3962.3
  Fernet Ops: 1000
  Fernet P50 Ms: 45.61
  Fernet P95 Ms: 53.03
  Hpke Miners: 256
  Hpke P50 Ms: 0.44
  Hpke P95 Ms: 0.51
  Duration S: 46.67
  Duration: 46.67s

D. RATE LIMITING UNDER LOAD (100 users × 20 msgs)
  Status:  ✅ PASS
  Total Requests: 2000
  Accepts: 1338
  Rejects: 662
  Reject Rate Pct: 33.1
  False Positives: 0
  False Negatives: 0
  Accuracy Pct: 100.0
  Duration S: 0.004
  Duration: 0.00s

E. MEMORY GRAPH GROWTH (100,000 memories)
  Status:  ✅ PASS
  Total Memories: 100000
  Total Users: 10000
  Insert Rate Ops Sec: 79745.0
  Insert P50 Ms: 0.001
  Insert P95 Ms: 0.002
  Query P50 Ms: 0.17
  Query P95 Ms: 0.25
  Query Trend: stable
  Rss Start Mb: 197.6
  Rss End Mb: 216.1
  Rss Growth Pct: 9.3
  Checkpoints: 20
  Duration S: 1.25
  Duration: 1.25s

F. VALIDATOR SCORING AT 256 SCALE
  Status:  ✅ PASS
  Miners: 256
  Rounds: 5
  Total Scored: 1280
  Scoring Throughput Miners Sec: 1707.3
  Round P50 Ms: 149.4
  Round P95 Ms: 153.6
  Weight Calc P50 Ms: 0.05
  Total Duration S: 0.75
  Duration: 0.75s

G. FULL PIPELINE INTEGRATION (1,000 users)
  Status:  ✅ PASS
  Users: 1000
  Pipeline Runs: 5462
  Errors: 0
  E2E P50 Ms: 90.6
  E2E P95 Ms: 274.4
  E2E P99 Ms: 542.2
  Store P50 Ms: 34.9
  Recall P50 Ms: 20.9
  Respond P50 Ms: 6.9
  Score P50 Ms: 0.02
  Pipeline Throughput: 71.2
  Duration S: 76.72
  Duration: 76.72s

═══════════════════════════════════════════════════════════════
  PERFORMANCE BENCHMARKS
═══════════════════════════════════════════════════════════════

  Chat success rate
    Required: >= 99%
    Actual:   99.87
    Result:   ✅ PASS

  Memory store p95 (load)
    Required: <= 150ms
    Actual:   20.64
    Result:   ✅ PASS

  Memory recall p95 (load)
    Required: <= 150ms
    Actual:   75.02
    Result:   ✅ PASS

  Encryption throughput
    Required: >= 1000/sec
    Actual:   5512.0
    Result:   ✅ PASS

  Rate limiter accuracy
    Required: >= 99.9%
    Actual:   100.0
    Result:   ✅ PASS

  256-miner scoring time
    Required: <= 5s
    Actual:   0.75
    Result:   ✅ PASS

  RSS memory growth
    Required: <= 10%
    Actual:   9.3
    Result:   ✅ PASS

═══════════════════════════════════════════════════════════════
  OVERALL SUMMARY
═══════════════════════════════════════════════════════════════

  Scenarios:   7/7 passed
  Benchmarks:  7/7 passed
  Total time:  1280.3s

  Verdict:     🟢 MAINNET READY

═══════════════════════════════════════════════════════════════