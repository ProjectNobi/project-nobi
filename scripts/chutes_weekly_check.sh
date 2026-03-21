#!/bin/bash
export CHUTES_API_KEY="REDACTED_CHUTES_KEY_6"
export CHUTES_MODEL="deepseek-ai/DeepSeek-V3.1-TEE"
cd /root/project-nobi
output=$(python3 scripts/chutes_model_check.py 2>&1)
# Only alert if new models found
if echo "$output" | grep -q "NEW MODELS FOUND"; then
  python3 -c "
import requests
msg = '''🆕 Weekly Chutes Model Check — New models detected!

$output
'''
requests.post('https://api.telegram.org/bot\$(cat /root/.openclaw/.env 2>/dev/null | grep TELEGRAM_BOT_TOKEN | cut -d= -f2)/sendMessage',
    json={'chat_id': '1602712596', 'text': msg[:4000]})
" 2>/dev/null
fi
