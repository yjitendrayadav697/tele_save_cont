"""
TechVJ/plugins/broadcast.py
Admin-only broadcast command with proper authorization checks.
"""

import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked

from config import ADMINS
from users_db import get_all_users

logger = logging.getLogger(__name__)

admin_filter = filters.private & filters.user(ADMINS)


@Client.on_message(admin_filter & filters.command("broadcast"))
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply("↩️ Reply to a message to broadcast it.")
        return

    target_msg = message.reply_to_message
    users      = await get_all_users()
    total      = len(users)

    if total == 0:
        await message.reply("No users to broadcast to.")
        return

    status = await message.reply(f"📢 Broadcasting to {total} users…")

    sent = failed = blocked = 0

    for user_id in users:
        try:
            await target_msg.copy(user_id)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value + 2)
            try:
                await target_msg.copy(user_id)
                sent += 1
            except Exception:
                failed += 1
        except (InputUserDeactivated, UserIsBlocked):
            blocked += 1
        except Exception as e:
            logger.warning(f"Broadcast failed for {user_id}: {e}")
            failed += 1

        # Throttle to avoid flood bans
        await asyncio.sleep(0.1)

    await status.edit(
        f"✅ Broadcast complete.\n"
        f"• Sent: {sent}\n"
        f"• Blocked/Deactivated: {blocked}\n"
        f"• Failed: {failed}"
    )
