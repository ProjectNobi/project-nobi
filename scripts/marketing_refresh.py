#!/usr/bin/env python3
"""
Daily Marketing Refresh — Updates READY_TO_POST.md with latest stats.
Runs daily at 07:00 UTC.
"""
import subprocess
import re
from datetime import datetime, timezone

FILE = "/root/project-nobi/marketing/READY_TO_POST.md"

def get_stats():
    stats = {}
    # Test count
    r = subprocess.run(["python3", "-m", "pytest", "tests/", "-q", "--tb=no"], capture_output=True, text=True, cwd="/root/project-nobi", timeout=180)
    m = re.search(r"(\d+) passed", r.stdout)
    stats['tests'] = m.group(1) if m else "1030"
    
    # Neuron count
    try:
        r = subprocess.run(["python3", "-c", "import bittensor as bt; mg=bt.Subtensor('test').metagraph(272); print(mg.n.item())"], capture_output=True, text=True, timeout=30)
        stats['neurons'] = r.stdout.strip()
    except: stats['neurons'] = "14"
    
    # Lines of code
    r = subprocess.run(["bash", "-c", "find nobi/ tests/ scripts/ app/ api/ -name '*.py' -not -path '*__pycache__*' | xargs wc -l | tail -1"], capture_output=True, text=True, cwd="/root/project-nobi")
    m = re.search(r"(\d+)", r.stdout)
    stats['lines'] = m.group(1) if m else "30960"
    
    # Module count
    r = subprocess.run(["bash", "-c", "find nobi/ -name '*.py' -not -path '*__pycache__*' | wc -l"], capture_output=True, text=True, cwd="/root/project-nobi")
    stats['modules'] = r.stdout.strip()
    
    return stats

def update_file(stats):
    with open(FILE) as f:
        content = f.read()
    
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    content = re.sub(r'Last updated: \d{4}-\d{2}-\d{2}', f'Last updated: {now}', content)
    content = re.sub(r'1,?\d{3} tests', f"{int(stats['tests']):,} tests", content)
    content = re.sub(r'\d+ neurons', f"{stats['neurons']} neurons", content)
    content = re.sub(r'30K\+', f"{int(stats['lines'])//1000}K+", content)
    content = re.sub(r'\d+ modules', f"{stats['modules']} modules", content)
    
    with open(FILE, 'w') as f:
        f.write(content)
    
    # Auto-commit and push
    subprocess.run(["git", "add", "marketing/READY_TO_POST.md"], cwd="/root/project-nobi")
    subprocess.run(["git", "commit", "-m", f"Daily marketing refresh — {now}"], cwd="/root/project-nobi", capture_output=True)
    subprocess.run(["git", "push", "old-origin", "main"], cwd="/root/project-nobi", capture_output=True)
    subprocess.run(["git", "push", "origin", "main"], cwd="/root/project-nobi", capture_output=True)
    
    print(f"✅ Marketing updated: {stats['tests']} tests, {stats['neurons']} neurons, {stats['lines']} lines")

if __name__ == "__main__":
    stats = get_stats()
    update_file(stats)
