"""
rate_limiter.py
Per-user in-memory rate limiter.
Prevents a single user from flooding the bot with requests.
"""

import time
import asyncio
from collections import defaultdict
from config import WAITING_TIME, MAX_CONCURRENT_USERS

# user_id → timestamp of their last accepted request
_last_request: dict[int, float] = defaultdict(float)

# user_id → whether they currently have an active task running
_active_tasks: dict[int, bool] = defaultdict(bool)

# Global count of concurrent active tasks
_active_count: int = 0
_lock = asyncio.Lock()


async def can_proceed(user_id: int) -> tuple[bool, str]:
    """
    Check whether a user is allowed to start a new request.
    Returns (allowed: bool, reason: str).
    """
    global _active_count

    async with _lock:
        now = time.monotonic()
        elapsed = now - _last_request[user_id]

        if _active_tasks[user_id]:
            return False, "You already have an active task running. Use /cancel to stop it."

        if elapsed < WAITING_TIME:
            remaining = int(WAITING_TIME - elapsed)
            return False, f"Please wait {remaining}s before sending another request."

        if _active_count >= MAX_CONCURRENT_USERS:
            return False, "The bot is busy right now. Please try again in a moment."

        # All checks passed — reserve the slot
        _last_request[user_id] = now
        _active_tasks[user_id] = True
        _active_count += 1
        return True, ""


async def release(user_id: int):
    """Call this when a user's task finishes or is cancelled."""
    global _active_count
    async with _lock:
        if _active_tasks[user_id]:
            _active_tasks[user_id] = False
            _active_count = max(0, _active_count - 1)
