"""
Project Nobi — Proactive Scheduler
====================================
Lightweight async scheduler that periodically checks all users
for proactive outreach opportunities and invokes a send callback.
"""

import asyncio
import logging
from typing import Callable, Awaitable, Optional

from nobi.proactive.engine import ProactiveEngine

logger = logging.getLogger("nobi-proactive-scheduler")


class ProactiveScheduler:
    """
    Background scheduler that runs ProactiveEngine checks periodically.

    Usage:
        scheduler = ProactiveScheduler(engine, send_callback)
        await scheduler.start(interval_seconds=3600)
        ...
        await scheduler.stop()
    """

    def __init__(
        self,
        engine: ProactiveEngine,
        send_callback: Callable[[str, str], Awaitable[None]],
    ):
        """
        Args:
            engine: ProactiveEngine instance.
            send_callback: Async callable(user_id, message) to send proactive messages.
        """
        self.engine = engine
        self.send_callback = send_callback
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def run_once(self) -> int:
        """
        Check all users for pending outreach, send messages, return count sent.
        """
        sent = 0
        try:
            outreach_items = self.engine.get_pending_outreach()

            for item in outreach_items:
                user_id = item["user_id"]
                message = item["message"]
                trigger = item["trigger"]

                try:
                    await self.send_callback(user_id, message)
                    self.engine.mark_sent(user_id, trigger.trigger_type, message)
                    sent += 1
                    logger.info(
                        f"[Proactive] Sent {trigger.trigger_type} to {user_id}: "
                        f"{message[:60]}..."
                    )
                except Exception as e:
                    logger.error(f"[Proactive] Failed to send to {user_id}: {e}")

        except Exception as e:
            logger.error(f"[Proactive] run_once error: {e}")

        if sent:
            logger.info(f"[Proactive] Sent {sent} proactive message(s)")
        return sent

    async def start(self, interval_seconds: int = 3600):
        """
        Start the background loop. Checks every interval_seconds.
        """
        if self._running:
            logger.warning("[Proactive] Scheduler already running")
            return

        self._running = True
        self._task = asyncio.ensure_future(self._loop(interval_seconds))
        logger.info(
            f"[Proactive] Scheduler started (interval={interval_seconds}s)"
        )

    async def stop(self):
        """Stop the background loop gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("[Proactive] Scheduler stopped")

    async def _loop(self, interval: int):
        """Internal loop — runs run_once then sleeps."""
        try:
            while self._running:
                try:
                    await self.run_once()
                except Exception as e:
                    logger.error(f"[Proactive] Loop error: {e}")

                # Sleep in small increments so we can stop quickly
                for _ in range(interval):
                    if not self._running:
                        break
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
