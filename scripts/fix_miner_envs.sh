#!/bin/bash
# Fix all nobi-uid-* miners to have proper CHUTES_API_KEY + CHUTES_MODEL in PM2 env
set +e

MODEL="moonshotai/Kimi-K2.5-TEE,deepseek-ai/DeepSeek-V3.2-TEE,MiniMaxAI/MiniMax-M2.5-TEE,zai-org/GLM-5-TEE,Qwen/Qwen3-32B-TEE:latency"

fix_server() {
    local ssh_target=$1
    local server_name=$2
    
    echo "=== $server_name ==="
    ssh -o ConnectTimeout=10 "$ssh_target" "
        cd /root/project-nobi
        for proc in \$(pm2 jlist 2>/dev/null | python3 -c '
import sys, json
procs = json.loads(sys.stdin.read())
for p in procs:
    if \"nobi-uid\" in p.get(\"name\", \"\"):
        print(p[\"name\"])
' 2>/dev/null); do
            uid=\${proc##*-}
            env_file=\"/root/project-nobi/.env.d/uid-\${uid}.env\"
            
            # Read API key from env file
            if [ -f \"\$env_file\" ]; then
                API_KEY=\$(grep '^CHUTES_API_KEY=' \"\$env_file\" | cut -d= -f2)
            else
                echo \"  SKIP \$proc — no env file\"
                continue
            fi
            
            if [ -z \"\$API_KEY\" ]; then
                echo \"  SKIP \$proc — no API key in env file\"
                continue
            fi
            
            # Get current script args
            ARGS=\$(pm2 show \$proc 2>/dev/null | grep 'script args' | sed 's/.*│ //;s/ *│\$//')
            
            if [ -z \"\$ARGS\" ]; then
                echo \"  SKIP \$proc — no args found\"
                continue
            fi
            
            # Delete and recreate with env vars
            pm2 delete \$proc 2>/dev/null
            CHUTES_API_KEY=\"\$API_KEY\" CHUTES_MODEL='$MODEL' pm2 start neurons/miner.py --name \$proc --interpreter python3 -- \$ARGS 2>/dev/null
            echo \"  ✅ \$proc — key=\${API_KEY:0:12}... model=set\"
        done
        pm2 save --force 2>/dev/null
    " 2>&1
}

# Also fix existing miners (nobi-miner-*, nobi-new-*)
fix_existing() {
    local ssh_target=$1
    local server_name=$2
    
    echo "=== $server_name (existing miners) ==="
    ssh -o ConnectTimeout=10 "$ssh_target" "
        cd /root/project-nobi
        for proc in \$(pm2 jlist 2>/dev/null | python3 -c '
import sys, json
procs = json.loads(sys.stdin.read())
for p in procs:
    name = p.get(\"name\", \"\")
    if (\"nobi-miner\" in name or \"nobi-new\" in name) and \"nobi-uid\" not in name:
        print(name)
' 2>/dev/null); do
            # Just set CHUTES_MODEL in env and restart
            CHUTES_MODEL='$MODEL' pm2 restart \$proc --update-env 2>/dev/null | tail -1
        done
        pm2 save --force 2>/dev/null
        echo 'done'
    " 2>&1 | grep -E "done|✓" | tail -1
}

# Fix uid miners on all servers
fix_server "server3" "Server3"
fix_server "server2" "Server2"  
fix_server "server4" "Server4"
fix_server "server5" "Server5"
fix_server "server6" "Server6"
fix_server "root@144.91.65.30" "AnonServer"

echo ""
echo "=== Fixing existing miners model chain ==="
fix_existing "server2" "Server2"
fix_existing "server3" "Server3"
fix_existing "server4" "Server4"
fix_existing "server5" "Server5"
fix_existing "server6" "Server6"
fix_existing "root@144.91.65.30" "AnonServer"

echo ""
echo "All done. Waiting 10s for startup..."
sleep 10

# Verify
echo ""
echo "=== VERIFICATION ==="
ssh -o ConnectTimeout=5 server3 "pm2 logs nobi-uid-31 --nostream --lines 20 2>/dev/null | grep -i 'Chutes client\|No API key\|model'" 2>&1
