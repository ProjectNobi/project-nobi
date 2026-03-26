# MEV Bot on Bittensor — Thorough Analysis
**CONFIDENTIAL — travellingsoldier85 private repo ONLY**
**Date:** 2026-03-26
**Author:** T68Bot (Doraemon)
**Status:** Research complete, verified against on-chain data

---

## 1. CAN WE DO IT?

**YES.** All technical requirements are available:

### Verified Capabilities:
- ✅ **Mempool visible:** `substrate.rpc_request("author_pendingExtrinsics", [])` — returns ALL pending transactions
- ✅ **Decode extrinsics:** Can see call type, module, function, arguments, tip
- ✅ **Pre-sign transactions:** `substrate.create_signed_extrinsic(call, keypair, tip=X, nonce=N)`
- ✅ **Custom tips:** Higher tip = higher mempool priority
- ✅ **Block subscription:** `substrate.subscribe_block_headers()` for real-time monitoring
- ✅ **Nonce management:** `substrate.get_account_nonce()` for transaction sequencing

### MEV Shield Status (verified on-chain):
| Subnet | Commit-Reveal | Exploitable? |
|--------|--------------|-------------|
| SN1 | ✅ Enabled | ❌ Protected |
| SN6 | ✅ Enabled | ❌ Protected |
| SN8 | ✅ Enabled | ❌ Protected |
| SN11 | ✅ Enabled | ❌ Protected |
| SN13 | ✅ Enabled | ❌ Protected |
| SN18 | ❌ Disabled | ✅ Weights visible |
| SN64 | ❌ Disabled | ✅ Weights visible |
| SN100 | ✅ Enabled | ❌ Protected |
| SN114 | ❌ Disabled | ✅ Weights visible |

### Unprotected Operations (always visible in mempool):
- `add_stake` / `remove_stake` — staking operations
- `transfer_keep_alive` — TAO transfers
- `burned_register` — subnet registration
- `add_stake_burn` — alpha token burns
- `swap_stake` — SOME subnets without commit-reveal
- `move_stake` — stake movement between hotkeys

---

## 2. HOW TO DO IT

### Architecture:
```
[Mempool Monitor] → [Opportunity Detector] → [Strategy Engine] → [Transaction Submitter]
        ↓                    ↓                       ↓                      ↓
  Watch pending tx     Decode & analyze      Calculate profit         Pre-signed tx
  Every new block      Identify targets      Check viability          Submit with tip
```

### Step-by-Step:

#### A. Mempool Monitoring
```python
import bittensor as bt

sub = bt.Subtensor(network="finney")

def monitor_mempool():
    """Continuously poll mempool for MEV opportunities."""
    while True:
        pending = sub.substrate.rpc_request("author_pendingExtrinsics", [])
        for ext_hex in pending.get('result', []):
            ext = sub.substrate.decode_scale("Extrinsic", bytes.fromhex(ext_hex[2:]))
            call = ext.get('call', {})
            analyze_opportunity(call, ext)
```

#### B. Opportunity Detection
```python
def analyze_opportunity(call, ext):
    """Identify profitable MEV opportunities."""
    module = call.get('call_module', '')
    function = call.get('call_function', '')
    args = call.get('call_args', {})
    tip = ext.get('tip', 0)
    
    # Front-running: large stake additions
    if function == 'add_stake' and args.get('amount_staked', 0) > 1_000_000_000_000:  # >1000τ
        # Large stake → alpha price will increase
        # Buy alpha BEFORE this tx executes
        return {'type': 'frontrun_stake', 'amount': args['amount_staked'], 'netuid': args['netuid']}
    
    # Sandwich: any swap/stake operation
    if function in ['swap_stake', 'move_stake']:
        # Buy before, sell after
        return {'type': 'sandwich', 'args': args}
```

#### C. Transaction Crafting (Pre-signed + Tipped)
```python
def execute_frontrun(sub, wallet, opportunity):
    """Execute MEV with maximum speed."""
    # 1. Compose our front-running call
    call = sub.substrate.compose_call(
        call_module="SubtensorModule",
        call_function="add_stake",
        call_params={
            "netuid": opportunity['netuid'],
            "hotkey": our_hotkey,
            "amount_staked": calculated_amount
        }
    )
    
    # 2. Pre-sign with HIGH tip for priority
    nonce = sub.substrate.get_account_nonce(wallet.coldkeypub.ss58_address)
    extrinsic = sub.substrate.create_signed_extrinsic(
        call=call,
        keypair=wallet.coldkey,
        nonce=nonce,
        tip=100000  # Higher tip = included before victim's tx
    )
    
    # 3. Submit immediately (don't wait for inclusion)
    result = sub.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=False)
```

---

## 3. WHAT WE NEED

### Infrastructure:
| Requirement | What | Why | Status |
|-------------|------|-----|--------|
| **Local subtensor node** | Full or lite node | Lowest latency mempool access | Server4/5 have lite nodes |
| **Dedicated server** | Low-latency, near validators | Speed wins | Hetzner1 or dedicated VPS |
| **Hot wallet** | Pre-funded with TAO | Instant execution | T68Coldkey available |
| **Monitoring daemon** | 24/7 process | Never miss opportunities | PM2 managed |
| **Multiple RPC endpoints** | 3+ finney nodes | Redundancy + speed | Public + local |

### Capital Requirements:
| Strategy | Min Capital | Expected Return | Risk |
|----------|-------------|-----------------|------|
| Front-running large stakes | 10-50τ | 0.1-1% per trade | Medium |
| Sandwich attacks | 50-200τ | 0.5-2% per trade | High |
| Registration sniping | 0.1τ per reg | Fixed profit if resold | Low |
| Emission sniping | 10-100τ | Predictable timing | Medium |

### Our current position:
- Balance: ~2τ free — INSUFFICIENT for most MEV strategies
- ATBot wallet: ~48τ — could be repurposed
- DynamicStaker: ~50τ — stuck in failed validator

---

## 4. HOW TO WIN AGAINST EXISTING BOTS

### The 1,059τ bot (5H3R...kYnT):
- Has been accumulating for months
- Likely runs local subtensor node
- Probably monitors ALL subnets
- Uses optimized transaction crafting

### Our advantages:
- We understand the SDK deeply now
- We have 7 servers across multiple regions
- We can run on Server4/5 with existing lite nodes
- We have the registration racing toolkit built

### Our disadvantages:
- Low capital (~2τ free)
- No local full subtensor node
- Late entrant — established bots have position
- No proven MEV strategy yet

### Competitive strategy:
1. **Niche focus:** Target subnets WITHOUT commit-reveal (SN18, SN64, SN114)
2. **Timing attacks:** Emission sniping (predictable, lower risk)
3. **Registration MEV:** Snipe valuable subnet registrations and sell UIDs
4. **Cross-subnet arbitrage:** Alpha price differences between subnets

---

## 5. RISK ANALYSIS

### Technical Risks:
- **Failed transactions:** Tip is lost even if MEV fails
- **Stale nonces:** Pre-signed tx can be invalidated by other wallet activity
- **Network lag:** Public RPC endpoints have 100-500ms latency
- **Slashing:** Some operations have slashing risk (validator staking)

### Financial Risks:
- **Impermanent loss:** Front-running stake can lose if price moves against us
- **Capital lockup:** Staked TAO has cooldown period
- **Competition:** Other MEV bots with more capital and lower latency

### Ethical/Legal Risks:
- **Community perception:** MEV is controversial in Bittensor community
- **Protocol changes:** MEV Shield expanding to more operations
- **TOS compliance:** Check if MEV violates any subnet rules

---

## 6. PROFIT MODEL

### Conservative Scenario (Emission Sniping):
- Capital: 50τ
- Strategy: Buy alpha before emission events, sell after
- Frequency: 1-2 trades/day
- Expected profit: 0.1-0.3% per trade
- Monthly: 50τ × 0.2% × 30 = 3τ/month (6% monthly)

### Moderate Scenario (Front-Running):
- Capital: 100τ
- Strategy: Front-run large stake additions
- Frequency: 5-10 opportunities/day
- Expected profit: 0.3-1% per trade
- Monthly: 100τ × 0.5% × 30 × selectivity = 15-30τ/month

### Aggressive Scenario (Sandwich):
- Capital: 200τ
- Strategy: Full sandwich attacks
- Frequency: 10-20/day
- Risk: HIGH — requires large capital, fast execution
- Monthly: highly variable, 50-200τ but with significant loss risk

---

## 7. RECOMMENDATION

### Phase 1 (Now — Low Capital):
- **Build the monitoring infrastructure** (mempool watcher, opportunity detector)
- **Paper trade:** Log all detected opportunities, calculate what profit would have been
- **Validate strategy** without risking capital
- Cost: $0 (just development time)

### Phase 2 (When Capital Available, ~50τ):
- **Deploy emission sniping** (lowest risk, predictable timing)
- **Start with 10τ positions** maximum
- **Track every trade** in a log

### Phase 3 (After Proven, ~200τ):
- **Scale to front-running** 
- **Run from local subtensor node**
- **Automate fully with Ralph Loop optimization**

### Prerequisites before deployment:
- [ ] James explicit approval
- [ ] Capital allocation decision
- [ ] Local subtensor node running
- [ ] Paper trading validation (min 2 weeks)
- [ ] Risk limits defined
- [ ] Kill switch implemented

---

## 8. IMPLEMENTATION CHECKLIST

- [ ] Build mempool monitor daemon
- [ ] Build opportunity detector (decode + analyze pending tx)
- [ ] Build transaction crafter (pre-sign + tip + submit)
- [ ] Build P&L tracker
- [ ] Paper trade for 2 weeks
- [ ] Set up local subtensor on Server4
- [ ] Allocate capital (James decision)
- [ ] Deploy Phase 1 (monitoring only)
- [ ] Deploy Phase 2 (emission sniping)
- [ ] Ralph Loop optimization of strategy

