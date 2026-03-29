#!/usr/bin/env python3
"""
MemoryBear Cron Runner.

Executed by PM2 cron jobs. Reads MEMORYBEAR_TASK env var to determine task:
  - reflection: Nightly conflict detection + flagging (run at 2am daily)
  - inference:  Weekly implicit memory inference (run Sunday 3am)
  - forgetting: Weekly ACT-R forgetting pass (run Saturday 4am)
"""

import asyncio
import logging
import os
import sys
import json
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("memorybear-cron")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = "~/.nobi/bot_memories.db"

TASK = os.environ.get("MEMORYBEAR_TASK", "reflection").lower()


async def main():
    logger.info(f"[MemoryBear Cron] Starting task: {TASK}")
    start = datetime.now(timezone.utc)

    if TASK == "reflection":
        from nobi.memory.reflection import run_reflection_cron
        result = await run_reflection_cron(db_path=DB_PATH)

    elif TASK == "inference":
        from nobi.memory.inference import run_inference_cron
        result = await run_inference_cron(db_path=DB_PATH)

    elif TASK == "forgetting":
        from nobi.memory.forgetting import run_forgetting_cron
        result = await run_forgetting_cron(db_path=DB_PATH)

    else:
        logger.error(f"Unknown MEMORYBEAR_TASK: {TASK}")
        sys.exit(1)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(f"[MemoryBear Cron] Task '{TASK}' complete in {elapsed:.1f}s. Result: {json.dumps(result)}")


if __name__ == "__main__":
    asyncio.run(main())
