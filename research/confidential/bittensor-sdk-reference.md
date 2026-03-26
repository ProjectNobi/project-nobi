# Bittensor SDK Complete Reference
## On-Chain Operations Playbook for Mining Operations

**Last Updated:** 2026-03-26  
**SDK Version:** bittensor 10.2.0  
**Network:** Finney (mainnet)

---

## Table of Contents
1. [Subtensor Core Methods](#subtensor-core-methods)
2. [Substrate Interface](#substrate-interface)
3. [Wallet Operations](#wallet-operations)
4. [btcli CLI Commands](#btcli-cli-commands)
5. [Metagraph & Chain Data](#metagraph--chain-data)
6. [Transaction Crafting](#transaction-crafting)
7. [Chain Queries](#chain-queries)
8. [Timing & Synchronization](#timing--synchronization)
9. [Practical Examples](#practical-examples)
10. [Common Gotchas](#common-gotchas)

---

## Subtensor Core Methods

### Registration Methods

#### `burned_register`
**What it does:** Registers a neuron on a subnet by burning TAO (recycling).
**When to use:** Standard registration for most subnets.
```python
# Register on subnet 114
result = sub.burned_register(
    wallet=wallet,
    netuid=114,
    wait_for_inclusion=True,
    wait_for_finalization=True
)
```

#### `register`
**What it does:** Alternative registration method (deprecated for most subnets).
**Gotcha:** Check subnet hyperparameters for which registration method is allowed.

#### `root_register`
**What it does:** Register as a root network validator.
**When to use:** Only for root network (netuid=0).

### Staking Methods

#### `add_stake`
**What it does:** Stake TAO to a hotkey.
**When to use:** Increase stake to improve ranking.
```python
# Stake 1.0 TAO to hotkey
result = sub.add_stake(
    wallet=wallet,
    netuid=114,
    hotkey_ss58=hotkey_ss58,
    amount=1.0,
    wait_for_inclusion=True
)
```

#### `add_stake_multiple`
**What it does:** Stake to multiple hotkeys in one transaction.
**When to use:** Efficient bulk staking.
```python
result = sub.add_stake_multiple(
    wallet=wallet,
    netuids=[114, 114],
    hotkey_ss58s=[hotkey1, hotkey2],
    amounts=[1.0, 2.0]
)
```

#### `unstake`
**What it does:** Unstake TAO from a hotkey.
**When to use:** Rebalance stake or exit subnet.
```python
result = sub.unstake(
    wallet=wallet,
    netuid=114,
    hotkey_ss58=hotkey_ss58,
    amount=0.5,
    wait_for_inclusion=True
)
```

### Weights Methods

#### `set_weights`
**What it does:** Set validator weights directly (legacy method).
**When to use:** Subnets without commit-reveal.
```python
result = sub.set_weights(
    wallet=wallet,
    netuid=114,
    uids=[1, 2, 3],
    weights=[0.5, 0.3, 0.2],
    wait_for_inclusion=True
)
```

#### `commit_weights`
**What it does:** Commit weights (first phase of commit-reveal).
**When to use:** Modern subnets with commit-reveal enabled.
```python
salt = bt.hash("random_salt")
result = sub.commit_weights(
    wallet=wallet,
    netuid=114,
    salt=salt,
    uids=[1, 2, 3],
    weights=[0.5, 0.3, 0.2]
)
```

#### `reveal_weights`
**What it does:** Reveal committed weights.
**When to use:** After commit_weights, within reveal period.
```python
result = sub.reveal_weights(
    wallet=wallet,
    netuid=114,
    salt=salt,  # Same salt used in commit
    uids=[1, 2, 3],
    weights=[0.5, 0.3, 0.2]
)
```

### Commitments Methods

#### `set_commitment`
**What it does:** Set commitment for a hotkey.
**When to use:** For commitment-based subnets (SN65+).
```python
result = sub.set_commitment(
    wallet=wallet,
    netuid=114,
    commitment=b"some_commitment"
)
```

#### `get_commitment`
**What it does:** Get commitment for a hotkey.
**When to use:** Check current commitment status.
```python
commitment = sub.get_commitment(netuid=114, hotkey_ss58=hotkey_ss58)
```

---

## Substrate Interface

### Transaction Crafting

#### `compose_call`
**What it does:** Create a call object for any extrinsic.
**When to use:** Low-level transaction building.
```python
call = sub.substrate.compose_call(
    call_module="SubtensorModule",
    call_function="add_stake",
    call_params={
        "netuid": 114,
        "hotkey": hotkey_ss58,
        "amount_staked": 1_000_000_000  # Planck
    }
)
```

#### `create_signed_extrinsic`
**What it does:** Create signed extrinsic from call.
**When to use:** Manual transaction signing.
```python
extrinsic = sub.substrate.create_signed_extrinsic(
    call=call,
    keypair=wallet.coldkey,
    era={"period": 64},
    nonce=nonce,
    tip=0
)
```

#### `submit_extrinsic`
**What it does:** Submit extrinsic to chain.
**When to use:** After creating signed extrinsic.
```python
result = sub.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
```

### Chain Queries

#### `query_storage`
**What it does:** Query any storage item.
**When to use:** Low-level chain state queries.
```python
# Query stake for hotkey
storage_key = sub.substrate.create_storage_key(
    pallet="SubtensorModule",
    storage_function="Stake",
    params=[114, hotkey_ss58]
)
result = sub.substrate.query_storage(storage_key)
```

#### `subscribe_block_headers`
**What it does:** Subscribe to new blocks.
**When to use:** Real-time block monitoring.
```python
def block_handler(block):
    print(f"New block: {block['header']['number']}")

sub.substrate.subscribe_block_headers(block_handler)
```

---

## Wallet Operations

### Key Methods

#### `create`
**What it does:** Create new wallet (coldkey + hotkey).
**When to use:** Setting up new mining identity.
```python
wallet = bt.Wallet.create(name="miner1", hotkey="miner1_hotkey")
```

#### `regen_coldkey`
**What it does:** Regenerate coldkey from mnemonic.
**When to use:** Recovering wallet on new machine.
```python
wallet = bt.Wallet.regen_coldkey(
    name="recovered",
    mnemonic="word1 word2 ... word12"
)
```

#### `regen_hotkey`
**What it does:** Regenerate hotkey from mnemonic.
**When to use:** Recovering hotkey.
```python
wallet = bt.Wallet.regen_hotkey(
    name="miner1",
    hotkey="recovered_hotkey",
    mnemonic="hotkey words..."
)
```

### Transaction Methods

#### `sign`
**What it does:** Sign message with wallet key.
**When to use:** Authentication or proof of ownership.
```python
signature = wallet.sign(b"message to sign")
```

#### `transfer`
**What it does:** Transfer TAO between addresses.
**When to use:** Moving funds between wallets.
```python
result = wallet.transfer(
    dest="5F3sa2T...",
    amount=10.0,
    wait_for_inclusion=True
)
```

---

## btcli CLI Commands

### Wallet Management
```bash
# List all wallets
btcli wallet list

# Create new coldkey
btcli wallet new-coldkey --wallet.name miner1

# Create new hotkey
btcli wallet new-hotkey --wallet.name miner1 --wallet.hotkey hotkey1

# Check balance
btcli wallet balance --wallet.name miner1

# Transfer TAO
btcli wallet transfer --wallet.name miner1 --dest 5F3sa2T... --amount 10.0
```

### Staking Operations
```bash
# Add stake
btcli stake add --wallet.name miner1 --netuid 114 --hotkey 5HK8T... --amount 1.0

# Remove stake
btcli stake remove --wallet.name miner1 --netuid 114 --hotkey 5HK8T... --amount 0.5

# List all stakes
btcli stake list --wallet.name miner1

# Move stake between hotkeys
btcli stake move --wallet.name miner1 --netuid 114 --from 5HK8T... --to 5HK9T... --amount 1.0
```

### Subnet Operations
```bash
# List all subnets
btcli subnet list

# Show subnet details
btcli subnet show --netuid 114

# Register on subnet
btcli subnet register --wallet.name miner1 --netuid 114

# Check subnet hyperparameters
btcli subnet hyperparameters --netuid 114
```

---

## Metagraph & Chain Data

### Metagraph Attributes
```python
mg = sub.metagraph(netuid=114)

# Key attributes for mining operations:
print(f"Total neurons: {len(mg.uids)}")
print(f"Active neurons: {sum(mg.active)}")
print(f"Stake per neuron: {mg.S}")  # Total stake
print(f"Rank (R): {mg.R}")  # Consensus rank
print(f"Trust (T): {mg.T}")  # Trust score
print(f"Dividends (D): {mg.D}")  # Emission dividends
print(f"Consensus (C): {mg.C}")  # Consensus score
print(f"Incentive (I): {mg.I}")  # Incentive score
print(f"Emission (E): {mg.E}")  # Total emission
```

### Hyperparameters (Critical for Mining)
```python
hparams = mg.hparams
print(f"Tempo: {hparams.tempo}")  # Blocks per epoch
print(f"Immunity period: {hparams.immunity_period}")  # Blocks before unstake
print(f"Burn amount: {hparams.burn}")  # Registration cost
print(f"Max validators: {hparams.max_validators}")
print(f"Min allowed weights: {hparams.min_allowed_weights}")
print(f"Weights rate limit: {hparams.weights_rate_limit}")
print(f"Commit reveal enabled: {hparams.commit_reveal_weights_enabled}")
```

### Neuron Information
```python
# Get specific neuron info
uid = 25
print(f"UID {uid}:")
print(f"  Hotkey: {mg.hotkeys[uid]}")
print(f"  Coldkey: {mg.coldkeys[uid]}")
print(f"  Stake: {mg.S[uid]:.2f} TAO")
print(f"  Rank: {mg.R[uid]:.6f}")
print(f"  Active: {bool(mg.active[uid])}")
print(f"  Axon: {mg.axons[uid]}")
```

---

## Transaction Crafting

### MEV Protection
```python
# Always use MEV protection for critical transactions
result = sub.add_stake(
    wallet=wallet,
    netuid=114,
    hotkey_ss58=hotkey_ss58,
    amount=1.0,
    mev_protection=True,  # Enable MEV protection
    period=64,  # Validity period in blocks
    wait_for_inclusion=True,
    wait_for_finalization=True
)
```

### Batch Transactions
```python
# Batch multiple stakes
result = sub.add_stake_multiple(
    wallet=wallet,
    netuids=[114, 115],
    hotkey_ss58s=[hotkey1, hotkey2],
    amounts=[1.0, 2.0],
    mev_protection=True
)
```

### Custom Extrinsic Building
```python
# Manual transaction flow
call = sub.substrate.compose_call(
    call_module="SubtensorModule",
    call_function="add_stake",
    call_params={
        "netuid": 114,
        "hotkey": hotkey_ss58,
        "amount_staked": int(1.0 * 1e9)  # TAO to Planck
    }
)

# Get nonce
nonce = sub.substrate.get_account_nonce(wallet.coldkey.ss58_address)

# Create and sign
extrinsic = sub.substrate.create_signed_extrinsic(
    call=call,
    keypair=wallet.coldkey.keypair,
    nonce=nonce,
    era={"period": 64},
    tip=0
)

# Submit
result = sub.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
```

---

## Chain Queries

### Balance & Stake Queries
```python
# Check coldkey balance
balance = sub.get_balance(coldkey_ss58)
print(f"Free balance: {balance.free:.6f} TAO")
print(f"Staked balance: {balance.staked:.6f} TAO")

# Get stake for specific hotkey
stake = sub.get_stake_for_coldkey_and_hotkey(
    coldkey_ss58=coldkey_ss58,
    hotkey_ss58=hotkey_ss58
)
print(f"Stake: {stake:.6f} TAO")

# Get all stakes for coldkey
all_stakes = sub.get_stake(coldkey_ss58)
for netuid, stakes in all_stakes.items():
    for hotkey, amount in stakes.items():
        print(f"netuid {netuid}, {hotkey}: {amount:.6f} TAO")
```

### Subnet Information
```python
# Get all subnets
subnets = sub.get_all_subnets_info()
for netuid, info in subnets.items():
    print(f"Subnet {netuid}:")
    print(f"  Name: {info.name}")
    print(f"  Emission: {info.emission:.6f} TAO/block")
    print(f"  Tempo: {info.tempo}")
    print(f"  Immunity: {info.immunity_period}")

# Get subnet owner
owner = sub.get_subnet_owner(netuid=114)
print(f"Subnet 114 owner: {owner}")

# Get subnet hyperparameters
params = sub.get_subnet_hyperparameters(netuid=114)
for key, value in params.items():
    print(f"{key}: {value}")
```

### Neuron & Validator Queries
```python
# Get all neurons on subnet
neurons = sub.neurons(netuid=114)
for neuron in neurons:
    print(f"UID {neuron.uid}: {neuron.hotkey}")

# Check if hotkey is registered
registered = sub.is_hotkey_registered(
    hotkey_ss58=hotkey_ss58,
    netuid=114
)
print(f"Registered: {registered}")

# Get validator permits
permits = sub.validator_permits(netuid=114)
print(f"Total validators: {len(permits)}")
print(f"Permits: {permits}")

# Check validator for UID
is_validator = sub.validator_for_uid(netuid=114, uid=25)
print(f"UID 25 is validator: {is_validator}")
```

---

## Timing & Synchronization

### Epoch Timing
```python
# Current block
current_block = sub.get_current_block()
print(f"Current block: {current_block}")

# Next epoch start
next_epoch_block = sub.get_next_epoch_start_block(netuid=114)
print(f"Next epoch starts at block: {next_epoch_block}")

# Blocks until next epoch
blocks_left = sub.blocks_until_next_epoch(netuid=114)
print(f"Blocks until next epoch: {blocks_left}")

# Wait for specific block
sub.wait_for_block(next_epoch_block)
print("Epoch started!")
```

### Immunity & Update Timing
```python
# Check immunity period
immunity = sub.immunity_period(netuid=114)
print(f"Immunity period: {immunity} blocks")

# Blocks since last update
uid = 25
blocks_since_update = sub.blocks_since_last_update(netuid=114, uid=uid)
print(f"Blocks since last update for UID {uid}: {blocks_since_update}")

# Check if in immunity
if blocks_since_update < immunity:
    print(f"UID {uid} still in immunity period")
else:
    print(f"UID {uid} can be updated")
```

### Tempo & Rate Limits
```python
# Get subnet tempo
tempo = sub.tempo(netuid=114)
print(f"Tempo: {tempo} blocks per epoch")

# Weight rate limit
rate_limit = sub.weights_rate_limit(netuid=114)
print(f"Weight rate limit: {rate_limit}")

# Check commit-reveal status
commit_reveal = sub.commit_reveal_enabled(netuid=114)
print(f"Commit-reveal enabled: {commit_reveal}")
```

---

## Practical Examples

### Complete Miner Setup
```python
import bittensor as bt
import time

# 1. Initialize
sub = bt.Subtensor(network="finney")
wallet = bt.Wallet(name="miner1", hotkey="miner1_hotkey")

# 2. Check registration
netuid = 114
if not sub.is_hotkey_registered(hotkey_ss58=wallet.hotkey.ss58_address, netuid=netuid):
    print("Not registered, registering...")
    result = sub.burned_register(
        wallet=wallet,
        netuid=netuid,
        wait_for_inclusion=True
    )
    print(f"Registration result: {result}")

# 3. Add stake
print("Adding stake...")
result = sub.add_stake(
    wallet=wallet,
    netuid=netuid,
    hotkey_ss58=wallet.hotkey.ss58_address,
    amount=1.0,
    wait_for_inclusion=True
)

# 4. Monitor position
mg = sub.metagraph(netuid=netuid)
uid = mg.hotkeys.index(wallet.hotkey.ss58_address)
print(f"Registered as UID {uid}")
print(f"Stake: {mg.S[uid]:.2f} TAO")
print(f"Rank: {mg.R[uid]:.6f}")
```

### Automated Weight Setting
```python
def set_weights_safely(sub, wallet, netuid, uids, weights):
    """Set weights with proper timing and checks."""
    
    # Check rate limit
    rate_limit = sub.weights_rate_limit(netuid=netuid)
    if len(uids) > rate_limit:
        print(f"Warning: {len(uids)} uids exceeds rate limit {rate_limit}")
        uids = uids[:rate_limit]
        weights = weights[:rate_limit]
    
    # Normalize weights
    total = sum(weights)
    if total > 0:
        weights = [w/total for w in weights]
    
    # Check commit-reveal
    if sub.commit_reveal_enabled(netuid=netuid):
        # Commit-reveal flow
        salt = bt.hash(str(time.time()))
        
        # Commit phase
        print("Committing weights...")
        result = sub.commit_weights(
            wallet=wallet,
            netuid=netuid,
            salt=salt,
            uids=uids,
            weights=weights
        )
        
        # Wait for reveal period
        time.sleep(30)
        
        # Reveal phase
        print("Revealing weights...")
        result = sub.reveal_weights(
            wallet=wallet,
            netuid=netuid,
            salt=salt,
            uids=uids,
            weights=weights
        )
    else:
        # Direct set weights
        print("Setting weights directly...")
        result = sub.set_weights(
            wallet=wallet,
            netuid=netuid,
            uids=uids,
            weights=weights,
            wait_for_inclusion=True
        )
    
    return result
```

### Stake Management Bot
```python
class StakeManager:
    def __init__(self, wallet_name, hotkey_name):
        self.sub = bt.Subtensor(network="finney")
        self.wallet = bt.Wallet(name=wallet_name, hotkey=hotkey_name)
    
    def rebalance_stake(self, netuid, target_stake=1.0):
        """Rebalance stake to target amount."""
        
        current_stake = self.sub.get_stake_for_coldkey_and_hotkey(
            coldkey_ss58=self.wallet.coldkey.ss58_address,
            hotkey_ss58=self.wallet.hotkey.ss58_address
        )
        
        diff = target_stake - current_stake
        
        if diff > 0:
            # Need to add stake
            print(f"Adding {diff:.6f} TAO stake...")
            result = self.sub.add_stake(
                wallet=self.wallet,
                netuid=netuid,
                hotkey_ss58=self.wallet.hotkey.ss58_address,
                amount=diff,
                wait_for_inclusion=True
            )
        elif diff < 0:
            # Need to remove stake
            print(f"Removing {abs(diff):.6f} TAO stake...")
            result = self.sub.unstake(
                wallet=self.wallet,
                netuid=netuid,
                hotkey_ss58=self.wallet.hotkey.ss58_address,
                amount=abs(diff),
                wait_for_inclusion=True
            )
        else:
            print("Stake already at target")
            result = None
        
        return result
    
    def monitor_and_adjust(self, netuid, check_interval=60):
        """Continuous stake monitoring."""
        while True:
            try:
                self.rebalance_stake(netuid)
                time.sleep(check_interval)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(check_interval * 2)
```

### Block Listener for Real-time Updates
```python
class BlockListener:
    def __init__(self, netuid):
        self.sub = bt.Subtensor(network="finney")
        self.netuid = netuid
        self.last_block = 0
        
    def on_new_block(self, block):
        block_number = block['header']['number']
        
        if block_number > self.last_block:
            self.last_block = block_number
            
            # Check if epoch transition
            blocks_until = self.sub.blocks_until_next_epoch(self.netuid)
            if blocks_until == 0:
                print(f"Block {block_number}: Epoch transition!")
                self.on_epoch_transition()
            
            # Update metagraph every 10 blocks
            if block_number % 10 == 0:
                self.update_metagraph()
    
    def on_epoch_transition(self):
        """Called on epoch transition."""
        mg = self.sub.metagraph(netuid=self.netuid)
        print(f"New epoch started. Total neurons: {len(mg.uids)}")
    
    def update_metagraph(self):
        """Update and analyze metagraph."""
        mg = self.sub.metagraph(netuid=self.netuid)
        active_count = sum(mg.active)
        print(f"Active neurons: {active_count}/{len(mg.uids)}")
    
    def start(self):
        """Start listening for blocks."""
        print(f"Starting block listener for subnet {self.netuid}")
        self.sub.substrate.subscribe_block_headers(self.on_new_block)
```

---

## Common Gotchas

### 1. Planck vs TAO Units
**Problem:** Confusion between TAO and Planck (1 TAO = 1e9 Planck).
**Solution:** Always check units in method signatures.
```python
# WRONG - passing TAO where Planck expected
sub.add_stake(amount=1.0)  # Actually expects Planck in some low-level methods

# CORRECT - use wrapper methods that handle conversion
sub.add_stake(amount=1.0)  # High-level method expects TAO

# For low-level, convert manually
amount_planck = int(1.0 * 1e9)
```

### 2. MEV Protection Timing
**Problem:** Transactions without MEV protection get front-run.
**Solution:** Always enable `mev_protection=True` for value transfers.
```python
# Vulnerable to MEV
sub.add_stake(..., mev_protection=False)

# Protected
sub.add_stake(..., mev_protection=True, period=64)
```

### 3. Rate Limits
**Problem:** Exceeding weight rate limits causes failed transactions.
**Solution:** Check `weights_rate_limit` before setting weights.
```python
rate_limit = sub.weights_rate_limit(netuid)
if len(uids) > rate_limit:
    uids = uids[:rate_limit]
    weights = weights[:rate_limit]
```

### 4. Immunity Period
**Problem:** Trying to update weights during immunity period.
**Solution:** Check `blocks_since_last_update` vs `immunity_period`.
```python
blocks_since = sub.blocks_since_last_update(netuid, uid)
immunity = sub.immunity_period(netuid)

if blocks_since < immunity:
    print(f"Wait {immunity - blocks_since} more blocks")
else:
    # Safe to update
    sub.set_weights(...)
```

### 5. Commit-Reveal Confusion
**Problem:** Using `set_weights` when commit-reveal is enabled.
**Solution:** Check `commit_reveal_enabled` first.
```python
if sub.commit_reveal_enabled(netuid):
    # Use commit_weights + reveal_weights
    salt = bt.hash("random")
    sub.commit_weights(salt=salt, ...)
    # Wait...
    sub.reveal_weights(salt=salt, ...)
else:
    # Use set_weights
    sub.set_weights(...)
```

### 6. Nonce Management
**Problem:** Concurrent transactions causing nonce conflicts.
**Solution:** Get fresh nonce for each transaction or use batch.
```python
# Get current nonce
nonce = sub.substrate.get_account_nonce(address)

# Or use high-level methods that handle nonce automatically
sub.add_stake(...)  # Automatically gets nonce
```

### 7. Connection Timeouts
**Problem:** Long-running scripts losing connection.
**Solution:** Implement reconnection logic.
```python
def with_retry(func, max_retries=3):
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            if i == max_retries - 1:
                raise
            print(f"Retry {i+1}/{max_retries}: {e}")
            time.sleep(2 ** i)  # Exponential backoff
```

### 8. Insufficient Balance for Fees
**Problem:** Transaction fails due to insufficient balance for fees.
**Solution:** Check balance and estimate fees first.
```python
balance = sub.get_balance(address)
if balance.free < 0.1:  # Keep minimum for fees
    print("Insufficient balance for fees")
    return

# Or use dry-run
try:
    result = sub.add_stake(..., wait_for_inclusion=False)
    print(f"Would cost approx: {result['partialFee']}")
except:
    print("Dry-run failed, check parameters")
```

---

## Quick Reference Cheat Sheet

### Essential Methods for Miners
```python
# Initialization
sub = bt.Subtensor("finney")
wallet = bt.Wallet("coldkey", "hotkey")

# Registration
sub.is_hotkey_registered(hotkey, netuid)
sub.burned_register(wallet, netuid)

# Staking
sub.add_stake(wallet, netuid, hotkey, amount)
sub.unstake(wallet, netuid, hotkey, amount)
sub.get_stake_for_coldkey_and_hotkey(coldkey, hotkey)

# Weights
if sub.commit_reveal_enabled(netuid):
    sub.commit_weights(wallet, netuid, salt, uids, weights)
    sub.reveal_weights(wallet, netuid, salt, uids, weights)
else:
    sub.set_weights(wallet, netuid, uids, weights)

# Monitoring
mg = sub.metagraph(netuid)
uid = mg.hotkeys.index(hotkey)
stake = mg.S[uid]
rank = mg.R[uid]

# Timing
sub.blocks_until_next_epoch(netuid)
sub.get_next_epoch_start_block(netuid)
sub.blocks_since_last_update(netuid, uid)
```

### Critical btcli Commands
```bash
# Monitor
btcli wallet balance --wallet.name <name>
btcli stake list --wallet.name <name>
btcli subnet show --netuid <netuid>

# Operations
btcli stake add --wallet.name <name> --netuid <netuid> --hotkey <hotkey> --amount <amount>
btcli subnet register --wallet.name <name> --netuid <netuid>

# Information
btcli subnet hyperparameters --netuid <netuid>
btcli subnet list
```

---

## Performance Tips

1. **Batch Operations:** Use `*_multiple` methods for bulk operations
2. **Connection Pooling:** Reuse Subtensor instance, don't create new ones
3. **Async Operations:** Use async/await for concurrent queries
4. **Caching:** Cache metagraph data, update periodically
5. **Error Handling:** Implement retry logic with exponential backoff
6. **Memory Management:** Clear large objects (metagraphs) when not needed
7. **Network Optimization:** Use local RPC endpoint if available

---

## Security Best Practices

1. **Never hardcode keys:** Use wallet files or env variables
2. **Use MEV protection:** Always for value transfers
3. **Validate parameters:** Check amounts, addresses before sending
4. **Test on testnet:** Always test new scripts on testnet first
5. **Monitor gas:** Set reasonable tips, monitor fee market
6. **Backup wallets:** Regular backups of coldkey mnemonics
7. **Use hardware wallets:** For large stakes, use hardware signers

---

This reference is maintained as a living document. Update with new patterns as the SDK evolves.