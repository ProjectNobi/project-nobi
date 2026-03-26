#!/bin/bash
# Deploy idle Nobi miners to non-Hetzner servers
# Directive: James 2026-03-25 — keep Hetzner1 free from new mining ops
# 28 idle UIDs distributed across 6 servers

set +e  # Don't exit on error — log and continue

# Server configs: server_alias ip chutes_key_index
# Keys: N4-N6=server2, N7-N9=server3, N10-N12=server4, N13-N15=server5, N16-N18=server6, N19-N21=anon
KEYS_FILE="/root/project-nobi/scripts/chutes_keys.txt"
mapfile -t KEYS < "$KEYS_FILE"

# Server definitions
declare -A SERVER_IP
SERVER_IP[server2]="217.77.4.142"
SERVER_IP[server3]="85.190.254.243"
SERVER_IP[server4]="213.199.61.137"
SERVER_IP[server5]="84.247.150.144"
SERVER_IP[server6]="194.163.179.223"
SERVER_IP[anon]="144.91.65.30"

declare -A SERVER_SSH
SERVER_SSH[server2]="server2"
SERVER_SSH[server3]="server3"
SERVER_SSH[server4]="server4"
SERVER_SSH[server5]="server5"
SERVER_SSH[server6]="server6"
SERVER_SSH[anon]="root@144.91.65.30"

# Distribute 28 miners across 6 servers
# AnonServer has most resources (18 CPU, 94GB) → 6 miners
# Server2 (12CPU/48GB), Server4 (12CPU/48GB), Server5 (12CPU/48GB) → 5 each
# Server3 (8CPU/24GB), Server6 (8CPU/24GB) → 3-4 each

# UID → hotkey wallet name → server assignment
# Format: UID HOTKEY_NAME SERVER PORT
ASSIGNMENTS=(
    # Server2 (5 miners) - ports 9003-9007
    "9 nobi-validator2 server2 9003"
    "27 nobi-val-004 server2 9004"
    "28 nobi-val-012 server2 9005"
    "29 nobi-val-013 server2 9006"
    "30 nobi-val-014 server2 9007"
    
    # Server3 (4 miners) - ports 9002-9005
    "31 nobi-val-015 server3 9002"
    "32 nobi-val-016 server3 9003"
    "33 nobi-val-017 server3 9004"
    "34 nobi-val-018 server3 9005"
    
    # Server4 (5 miners) - ports 9003-9007
    "35 nobi-val-019 server4 9003"
    "36 nobi-val-020 server4 9004"
    "37 nobi-miner-001 server4 9005"
    "38 nobi-miner-002 server4 9006"
    "39 nobi-miner-003 server4 9007"
    
    # Server5 (5 miners) - ports 9003-9007
    "40 nobi-miner-004 server5 9003"
    "41 nobi-miner-005 server5 9004"
    "42 nobi-miner-006 server5 9005"
    "43 nobi-miner-007 server5 9006"
    "44 nobi-miner-008 server5 9007"
    
    # Server6 (4 miners) - ports 9001-9004
    "45 nobi-miner-009 server6 9001"
    "46 nobi-miner-010 server6 9002"
    "47 nobi-miner-011 server6 9003"
    "48 nobi-miner-012 server6 9004"
    
    # AnonServer (5 miners) - ports 9004-9008
    "49 nobi-miner-013 anon 9004"
    "50 nobi-miner-014 anon 9005"
    "51 nobi-miner-015 anon 9006"
    "52 nobi-miner-016 anon 9007"
    "53 nobi-miner-017 anon 9008"
)

# Key assignment per server (round-robin from allocated keys)
declare -A SERVER_KEY_IDX
SERVER_KEY_IDX[server2]=3   # N4 (0-indexed: key 3)
SERVER_KEY_IDX[server3]=6   # N7
SERVER_KEY_IDX[server4]=9   # N10
SERVER_KEY_IDX[server5]=12  # N13
SERVER_KEY_IDX[server6]=15  # N16
SERVER_KEY_IDX[anon]=18     # N19

deploy_miner() {
    local uid=$1
    local hotkey=$2
    local server=$3
    local port=$4
    
    local ssh_target="${SERVER_SSH[$server]}"
    local ip="${SERVER_IP[$server]}"
    local key_idx="${SERVER_KEY_IDX[$server]}"
    local api_key="${KEYS[$key_idx]}"
    local pm2_name="nobi-uid-${uid}"
    
    echo "Deploying UID $uid ($hotkey) → $server ($ip:$port)..."
    
    # 1. Copy hotkey wallet file if not present
    local hotkey_file="/root/.bittensor/wallets/T68Coldkey/hotkeys/$hotkey"
    ssh -o ConnectTimeout=10 "$ssh_target" "test -f $hotkey_file" 2>/dev/null || {
        echo "  Copying hotkey $hotkey to $server..."
        scp -o ConnectTimeout=10 "$hotkey_file" "$ssh_target:$hotkey_file" 2>/dev/null
    }
    
    # 2. Create env file
    ssh -o ConnectTimeout=10 "$ssh_target" "echo 'CHUTES_API_KEY=$api_key' > /root/project-nobi/.env.d/uid-${uid}.env"
    
    # 3. Start miner via pm2
    ssh -o ConnectTimeout=10 "$ssh_target" "cd /root/project-nobi && pm2 delete $pm2_name 2>/dev/null; pm2 start /root/bt_venv/bin/python3 --name $pm2_name -- neurons/miner.py --wallet.name T68Coldkey --wallet.hotkey $hotkey --subtensor.network test --netuid 272 --axon.port $port --axon.external_ip $ip --axon.external_port $port --logging.debug && pm2 save --force" 2>&1
    
    echo "  ✅ UID $uid deployed on $server:$port"
}

echo "============================================="
echo "Deploying 28 idle Nobi miners to 6 servers"
echo "============================================="
echo ""

FAILED=0
SUCCESS=0

for assignment in "${ASSIGNMENTS[@]}"; do
    read -r uid hotkey server port <<< "$assignment"
    if deploy_miner "$uid" "$hotkey" "$server" "$port"; then
        ((SUCCESS++))
    else
        echo "  ❌ FAILED: UID $uid"
        ((FAILED++))
    fi
    echo ""
done

echo "============================================="
echo "Deployment complete: $SUCCESS success, $FAILED failed"
echo "============================================="
