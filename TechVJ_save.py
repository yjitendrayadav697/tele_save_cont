"""
TechVJ/plugins/save.py
Main handler for saving restricted Telegram content.
Includes rate limiting, input validation, cancellation support,
and safe error handling.
"""

import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait, ChannelPrivate, ChatAdminRequired,
    MessageIdInvalid, UsernameInvalid, UserNotParticipant,
)

from config import ADMINS, CHANNEL_ID, WAITING_TIME, ERROR_MESSAGE
from rate_limiter import can_proceed, release
from validators import validate_link
from bot import TechVJUser
from database.users_db import get_user_session, is_user_logged_in

logger = logging.getLogger(__name__)

# Tracks active cancel requests per user
_cancel_flags: dict[int, bool] = {}


def _is_cancelled(user_id: int) -> bool:
    return _cancel_flags.get(user_id, False)


def _set_cancel(user_id: int, value: bool):
    _cancel_flags[user_id] = value


# ── /cancel command ───────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("cancel"))
async def cancel_handler(client: Client, message: Message):
    user_id = message.from_user.id
    _set_cancel(user_id, True)
    await message.reply("⚠️ Cancellation requested. Your current task will stop shortly.")


# ── Main link handler ─────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.text & ~filters.command(
    ["start", "help", "login", "logout", "cancel", "broadcast"]
))
async def save_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text    = message.text.strip()

    # ── 1. Validate the link ──────────────────────────────────────────────────
    parsed, error = validate_link(text)
    if error:
        await message.reply(f"❌ {error}")
        return

    # ── 2. Rate limiting ──────────────────────────────────────────────────────
    allowed, reason = await can_proceed(user_id)
    if not allowed:
        await message.reply(f"⏳ {reason}")
        return

    # ── 3. Resolve which user client to use ───────────────────────────────────
    user_client = await _resolve_user_client(user_id, client, message)
    if user_client is None:
        await release(user_id)
        return

    # ── 4. Process the request ────────────────────────────────────────────────
    _set_cancel(user_id, False)
    status_msg = await message.reply(
        f"⏳ Processing {parsed.end_id - parsed.start_id + 1} message(s)…\n"
        "Send /cancel to stop."
    )

    try:
        await _process_posts(client, user_client, message, parsed, status_msg)
    except Exception as e:
        logger.exception(f"Unhandled error for user {user_id}: {e}")
        await status_msg.edit("❌ An unexpected error occurred. Please try again later.")
        if ERROR_MESSAGE and ADMINS:
            try:
                await client.send_message(
                    ADMINS[0],
                    f"⚠️ Error for user `{user_id}`:\n`{type(e).__name__}: {e}`"
                )
            except Exception:
                pass
    finally:
        await release(user_id)
        _set_cancel(user_id, False)


async def _resolve_user_client(
    user_id: int, bot: Client, message: Message
) -> Client | None:
    """
    Return the appropriate Pyrogram user Client for this request.
    - If LOGIN_SYSTEM is on:  use the session stored in DB for this user.
    - If LOGIN_SYSTEM is off: use the global TechVJUser client.
    Returns None and notifies the user if no valid client is available.
    """
    from config import LOGIN_SYSTEM

    if not LOGIN_SYSTEM:
        if TechVJUser is None:
            await message.reply("❌ Bot is not configured correctly. Contact the admin.")
            return None
        return TechVJUser

    # LOGIN_SYSTEM is True — need a per-user session
    if not await is_user_logged_in(user_id):
        await message.reply(
            "🔐 You need to log in first.\n"
            "Use /login to authenticate with your Telegram account."
        )
        return None

    session_string = await get_user_session(user_id)
    if not session_string:
        await message.reply("❌ Session not found. Please /login again.")
        return None

    from pyrogram import Client as PyroClient
    from config import API_ID, API_HASH
    user_client = PyroClient(
        f"user_{user_id}",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session_string,
        in_memory=True,
    )
    await user_client.start()
    return user_client


async def _process_posts(
    bot: Client,
    user_client: Client,
    message: Message,
    parsed,
    status_msg: Message,
):
    """Fetch and forward posts one by one with flood protection and cancellation."""
    user_id   = message.from_user.id
    success   = 0
    failed    = 0
    total     = parsed.end_id - parsed.start_id + 1

    for msg_id in range(parsed.start_id, parsed.end_id + 1):
        if _is_cancelled(user_id):
            await status_msg.edit(
                f"🛑 Cancelled after {success}/{total} messages."
            )
            return

        try:
            if parsed.is_private:
                chat_ref = int(f"-100{parsed.chat}")
            else:
                chat_ref = parsed.chat

            msg = await user_client.get_messages(chat_ref, msg_id)

            if msg is None or msg.empty:
                failed += 1
                continue

            dest = int(CHANNEL_ID) if CHANNEL_ID else message.chat.id
            await user_client.copy_message(
                chat_id=dest,
                from_chat_id=chat_ref,
                message_id=msg_id,
            )
            success += 1

        except FloodWait as e:
            wait = min(e.value + 5, 60)   # cap at 60s
            logger.warning(f"FloodWait {e.value}s — sleeping {wait}s")
            await asyncio.sleep(wait)
            failed += 1

        except (ChannelPrivate, ChatAdminRequired, UserNotParticipant):
            await status_msg.edit(
                "❌ Cannot access this chat. Make sure the account is a member."
            )
            return

        except (MessageIdInvalid, UsernameInvalid):
            failed += 1

        except Exception as e:
            logger.error(f"Error on message {msg_id}: {e}")
            failed += 1

        await asyncio.sleep(WAITING_TIME)

    await status_msg.edit(
        f"✅ Done! {success}/{total} message(s) saved."
        + (f"\n⚠️ {failed} failed." if failed else "")
    )
