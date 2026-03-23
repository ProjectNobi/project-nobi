# Project Nobi — 256-Neuron Deployment Guide

Deploy 256 neurons (20 validators + 236 miners) across 6 servers on Bittensor testnet subnet 272.

---

## Quick Start

```bash
cd /root/project-nobi

# 1. Preview everything (no changes made)
python3 scripts/deploy_256.py --dry-run

# 2. Phase 1 only — generate all hotkeys
python3 scripts/deploy_256.py --phase hotkeys

# 3. Phase 2 — register all UIDs (~48 min, takes 239 blocks)
python3 scripts/deploy_256.py --phase register

# 4. Phase 3 — SCP hotkeys + generate PM2 configs
python3 scripts/deploy_256.py --phase distribute

# 5. Phase 4 — start all PM2 processes
python3 scripts/deploy_256.py --phase start

# Or run all phases in sequence:
python3 scripts/deploy_256.py --phase all
```

---

## Files

| File | Purpose |
|------|---------|
| `deploy_256.py` | Main deployment script |
| `chutes_keys.txt` | Chutes API keys (one per line) |
| `server_config.json` | Server assignments + port ranges |
| `deploy_256_state.json` | Auto-created: tracks progress |
| `deploy_256.log` | Auto-created: full log |
| `ecosystem_*.config.js` | Auto-generated per server (after Phase 3) |

---

## Server Distribution

| Server | SSH Host | Miners | Validators | Miner Range | Val Range |
|--------|----------|--------|------------|-------------|-----------|
| ContaboServer2 | server2 | 50 | 4 | 001–050 | 01–04 |
| ContaboServer3 | server3 | 25 | 3 | 051–075 | 05–07 |
| ContaboServer4 | server4 | 50 | 4 | 076–125 | 08–11 |
| ContaboServer5 | server5 | 50 | 4 | 126–175 | 12–15 |
| ContaboServer6 | server6 | 11 | 2 | 176–186 | 16–17 |
| AnonServer | anonserver | 50 | 3 | 187–236 | 18–20 |
| **Total** | | **236** | **20** | | |

---

## Phase Details

### Phase 1: Generate Hotkeys
- Creates hotkeys under `T68Coldkey`: `nobi-miner-001` through `nobi-miner-236`, `nobi-val-001` through `nobi-val-020`
- Skips any that already exist (idempotent)
- Stored at: `~/.bittensor/wallets/T68Coldkey/hotkeys/`

### Phase 2: Register UIDs
- Registers each hotkey on testnet SN272 via burn registration
- **One registration per block** — 14s delay between each
- **~239 registrations × 14s ≈ 56 minutes**
- Burn cost: ~τ0.021 per UID × 239 ≈ **τ5.0 total**
- Resume-safe: checks state file + on-chain registry before each registration
- If interrupted, re-run `--phase register` — it picks up where it left off

### Phase 3: Distribute
- SCPs all hotkey files to each target server's `~/.bittensor/wallets/T68Coldkey/hotkeys/`
- Generates per-server `ecosystem.config.js` PM2 config
- Also SCPs ecosystem config to `{repo_path}/ecosystem.config.js` on each server
- Verifies/updates the project-nobi repo on each server

### Phase 4: Start
- SSHs to each server and runs `pm2 start ecosystem.config.js`
- Saves PM2 process list (`pm2 save`)
- Reports online process count per server

---

## Port Allocation

- **Validators**: ports 8000, 8001, 8002, ... (per server, restarting from 8000 on each)
- **Miners**: ports 9000, 9001, 9002, ... (per server, restarting from 9000 on each)

---

## Chutes API Keys

Keys are read from `scripts/chutes_keys.txt` — one per line.
Distributed round-robin across all neurons.

To add more keys:
```bash
echo "cpk_your_new_key_here" >> /root/project-nobi/scripts/chutes_keys.txt
```

Currently 9 keys → will be expanded to 29 keys when 20 more are added.

---

## Status & Monitoring

```bash
# Check deployment state
python3 scripts/deploy_256.py --status

# View live log
tail -f scripts/deploy_256.log

# After deployment: check PM2 on a server
ssh server2 "pm2 list"
ssh server2 "pm2 logs nobi-miner-001 --lines 50"

# Check all servers at once
for s in server2 server3 server4 server5 server6 "anonserver"; do
  echo "=== $s ==="; ssh $s "pm2 list --no-color 2>/dev/null | grep -c online"; done
```

---

## Re-Running / Recovery

The script is **fully idempotent** — safe to re-run at any point.

```bash
# Re-run a specific phase
python3 scripts/deploy_256.py --phase register

# Force re-run a phase that was marked complete
python3 scripts/deploy_256.py --reset-phase distribute
python3 scripts/deploy_256.py --phase distribute
```

State is saved after every registration, so if Phase 2 is interrupted (e.g., network error), just re-run `--phase register` — it will skip already-registered hotkeys and continue from where it left off.

---

## Prerequisites

On Hetzner1 (this machine):
- `bittensor` Python package installed
- `T68Coldkey` wallet present at `~/.bittensor/wallets/`
- SSH access configured for all 6 target servers

On target servers (auto-handled by Phase 3/4):
- `project-nobi` repo cloned at `/root/project-nobi`
- `requirements.txt` installed
- `pm2` installed (installed automatically if missing)

---

## Neuron Counts

| Type | Count | Hotkey Names |
|------|-------|-------------|
| Validators | 20 | nobi-val-001 through nobi-val-020 |
| Miners | 236 | nobi-miner-001 through nobi-miner-236 |
| **Total** | **256** | |

---

## Estimated Costs

| Item | Cost |
|------|------|
| Burn per UID | ~τ0.021 |
| 239 registrations | ~τ5.02 |
| Current balance | τ46.13 |
| Remaining after | ~τ41.11 |

---

## Important Notes

1. **DO NOT run on Hetzner1's PM2** — all neurons run on the 6 target servers
2. **DO NOT run on any testnet subnet except 272**
3. Phase 2 takes ~56 minutes — keep your SSH session alive or run in `tmux`
4. Hotkey files are NOT stored on remote servers in `~/.bittensor` cold storage — they're distributed hotkeys only
5. Coldkey remains on Hetzner1 only — never copied to any other server

---

## Tmux Recommended for Phase 2

```bash
tmux new -s nobi-deploy
cd /root/project-nobi
python3 scripts/deploy_256.py --phase register
# Ctrl+B D to detach, tmux attach -t nobi-deploy to reattach
```
