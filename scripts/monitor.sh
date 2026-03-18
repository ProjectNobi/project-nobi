#!/bin/bash
# Project Nobi — Live Monitor
# Shows on-chain state + PM2 status

NETUID=272
NETWORK="test"

while true; do
    clear
    echo "===== Project Nobi — SN$NETUID Live Monitor ====="
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo ""

    # Metagraph
    python3 -c "
import bittensor as bt
sub = bt.Subtensor(network='$NETWORK')
mg = sub.metagraph($NETUID)
print(f'Neurons: {mg.n}  |  Block: {sub.get_current_block()}')
print('')
print(f'{'UID':>4}  {'Hotkey':>20}  {'Stake':>12}  {'Incentive':>10}  {'Active':>7}  {'VPermit':>8}')
print('-' * 70)
for uid in range(mg.n):
    hk = mg.hotkeys[uid][:18] + '..'
    stake = float(mg.S[uid])
    inc = float(mg.I[uid])
    active = '✅' if mg.active[uid] else '❌'
    vp = '✅' if mg.validator_permit[uid] else '  '
    print(f'{uid:>4}  {hk:>20}  {stake:>12.4f}  {inc:>10.6f}  {active:>7}  {vp:>8}')
" 2>/dev/null

    echo ""
    echo "----- PM2 Status -----"
    pm2 jlist 2>/dev/null | python3 -c "
import json, sys
procs = json.load(sys.stdin)
nobi = [p for p in procs if 'nobi' in p.get('name','')]
if not nobi:
    print('  No nobi processes running')
for p in nobi:
    name = p['name']
    status = p['pm2_env']['status']
    uptime = p['pm2_env'].get('pm_uptime', 0)
    restarts = p['pm2_env']['restart_time']
    print(f'  {name}: {status}  restarts={restarts}')
" 2>/dev/null

    echo ""
    echo "(Ctrl+C to exit — refreshing every 30s)"
    sleep 30
done
