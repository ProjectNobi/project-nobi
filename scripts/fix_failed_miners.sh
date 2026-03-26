#!/bin/bash
# Fix miners that failed to start on server3/4/5/6 (wrong python path)
# and AnonServer (missing .env.d)
set +e

KEYS_FILE="/root/project-nobi/scripts/chutes_keys.txt"
mapfile -t KEYS < "$KEYS_FILE"

fix_miner() {
    local uid=$1
    local hotkey=$2
    local ssh_target=$3
    local ip=$4
    local port=$5
    local key=$6
    local pm2_name="nobi-uid-${uid}"
    
    echo "Fixing UID $uid ($hotkey) on $ssh_target ($ip:$port)..."
    
    # Create env file
    ssh -o ConnectTimeout=10 "$ssh_target" "mkdir -p /root/project-nobi/.env.d && echo 'CHUTES_API_KEY=$key' > /root/project-nobi/.env.d/uid-${uid}.env" 2>&1
    
    # Delete old failed process and start with correct interpreter
    ssh -o ConnectTimeout=10 "$ssh_target" "cd /root/project-nobi && pm2 delete $pm2_name 2>/dev/null; pm2 start neurons/miner.py --name $pm2_name --interpreter python3 -- --wallet.name T68Coldkey --wallet.hotkey $hotkey --subtensor.network test --netuid 272 --axon.port $port --axon.external_ip $ip --axon.external_port $port --logging.debug && pm2 save --force" 2>&1
    
    echo "  ✅ UID $uid fixed"
}

echo "============================================="
echo "Fixing failed miner deployments"
echo "============================================="

# Server3 (key index 6 = N7) - UIDs 31-34
for i in 31:nobi-val-015:9002 32:nobi-val-016:9003 33:nobi-val-017:9004 34:nobi-val-018:9005; do
    IFS=: read uid hk port <<< "$i"
    fix_miner "$uid" "$hk" "server3" "85.190.254.243" "$port" "${KEYS[6]}"
done

# Server4 (key index 9 = N10) - UIDs 35-39
for i in 35:nobi-val-019:9003 36:nobi-val-020:9004 37:nobi-miner-001:9005 38:nobi-miner-002:9006 39:nobi-miner-003:9007; do
    IFS=: read uid hk port <<< "$i"
    fix_miner "$uid" "$hk" "server4" "213.199.61.137" "$port" "${KEYS[9]}"
done

# Server5 (key index 12 = N13) - UIDs 40-44
for i in 40:nobi-miner-004:9003 41:nobi-miner-005:9004 42:nobi-miner-006:9005 43:nobi-miner-007:9006 44:nobi-miner-008:9007; do
    IFS=: read uid hk port <<< "$i"
    fix_miner "$uid" "$hk" "server5" "84.247.150.144" "$port" "${KEYS[12]}"
done

# Server6 (key index 15 = N16) - UIDs 45-48
for i in 45:nobi-miner-009:9001 46:nobi-miner-010:9002 47:nobi-miner-011:9003 48:nobi-miner-012:9004; do
    IFS=: read uid hk port <<< "$i"
    fix_miner "$uid" "$hk" "server6" "194.163.179.223" "$port" "${KEYS[15]}"
done

# AnonServer (key index 18 = N19) - fix env files for UIDs 49-53
for i in 49:nobi-miner-013:9004 50:nobi-miner-014:9005 51:nobi-miner-015:9006 52:nobi-miner-016:9007 53:nobi-miner-017:9008; do
    IFS=: read uid hk port <<< "$i"
    # Just fix the env file — miners already started fine on anon
    ssh -o ConnectTimeout=10 "root@144.91.65.30" "mkdir -p /root/project-nobi/.env.d && echo 'CHUTES_API_KEY=${KEYS[18]}' > /root/project-nobi/.env.d/uid-${uid}.env" 2>&1
    echo "  ✅ UID $uid env fixed on AnonServer"
done

echo ""
echo "============================================="
echo "All fixes applied"
echo "============================================="
