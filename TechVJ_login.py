"""
TechVJ/plugins/login.py
Secure login flow using Pyrogram's in-memory client.
- OTP sent directly via Telegram (never stored or logged)
- Session string encrypted before saving to DB
- Login state tracked per-user with timeouts
- Sensitive messages auto-deleted after a short delay
"""

import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired,
    SessionPasswordNeeded, PasswordHashInvalid, FloodWait,
)

from config import API_ID, API_HASH
from users_db import (
    save_user_session, delete_user_session, is_user_logged_in
)

logger = logging.getLogger(__name__)

# Tracks users currently in the login flow: user_id → step
_login_state: dict[int, dict] = {}

LOGIN_TIMEOUT = 120  # seconds before a login attempt expires


async def _delete_after(message: Message, delay: int = 30):
    """Delete a sensitive message after `delay` seconds."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


# ── /login ────────────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("login"))
async def login_cmd(client: Client, message: Message):
    user_id = message.from_user.id

    if await is_user_logged_in(user_id):
        await message.reply("✅ You are already logged in. Use /logout to sign out.")
        return

    if user_id in _login_state:
        await message.reply("⏳ You already have a login in progress. Send your phone number or /cancel.")
        return

    _login_state[user_id] = {"step": "phone"}
    prompt = await message.reply(
        "📱 Please send your phone number in international format.\n"
        "Example: `+919876543210`\n\n"
        "Send /cancel to abort."
    )

    # Auto-expire the login session after LOGIN_TIMEOUT seconds
    asyncio.create_task(_expire_login(user_id, LOGIN_TIMEOUT))


@Client.on_message(filters.private & filters.command("cancel"))
async def cancel_login(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in _login_state:
        state = _login_state.pop(user_id)
        # Clean up any temporary pyrogram client
        temp_client = state.get("client")
        if temp_client:
            try:
                await temp_client.stop()
            except Exception:
                pass
        await message.reply("❌ Login cancelled.")


@Client.on_message(filters.private & filters.text & ~filters.command([
    "start", "help", "login", "logout", "cancel", "broadcast"
]))
async def login_step_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id not in _login_state:
        return  # Not in login flow — let other handlers process

    state = _login_state[user_id]
    step  = state.get("step")

    # ── Step 1: Receive phone number ──────────────────────────────────────────
    if step == "phone":
        phone = message.text.strip()
        # Delete the message containing the phone number immediately
        asyncio.create_task(_delete_after(message, delay=3))

        if not phone.startswith("+") or not phone[1:].isdigit():
            await message.reply("❌ Invalid format. Use international format e.g. `+919876543210`.")
            return

        temp_client = Client(
            f"login_{user_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True,
        )

        try:
            await temp_client.connect()
            sent_code = await temp_client.send_code(phone)
        except PhoneNumberInvalid:
            await message.reply("❌ That phone number is invalid.")
            _login_state.pop(user_id, None)
            return
        except FloodWait as e:
            await message.reply(f"⏳ Too many attempts. Please wait {e.value} seconds.")
            _login_state.pop(user_id, None)
            return
        except Exception as e:
            logger.error(f"Login error (phone step) for {user_id}: {e}")
            await message.reply("❌ An error occurred. Please try again later.")
            _login_state.pop(user_id, None)
            return

        state.update({
            "step": "otp",
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
            "client": temp_client,
        })
        otp_prompt = await message.reply(
            "✉️ An OTP has been sent to your Telegram account.\n"
            "Please send the OTP code.\n\n"
            "⚠️ This message will be deleted in 60 seconds for your security."
        )
        asyncio.create_task(_delete_after(otp_prompt, delay=60))

    # ── Step 2: Receive OTP ───────────────────────────────────────────────────
    elif step == "otp":
        otp = message.text.strip().replace(" ", "")
        asyncio.create_task(_delete_after(message, delay=3))  # Delete OTP immediately

        temp_client = state.get("client")
        phone       = state.get("phone")
        phone_code_hash = state.get("phone_code_hash")

        try:
            await temp_client.sign_in(phone, phone_code_hash, otp)
        except PhoneCodeInvalid:
            await message.reply("❌ Invalid OTP. Please try again.")
            return
        except PhoneCodeExpired:
            await message.reply("❌ OTP expired. Please /login again.")
            _login_state.pop(user_id, None)
            return
        except SessionPasswordNeeded:
            state["step"] = "2fa"
            await message.reply("🔐 Two-factor authentication is enabled. Please send your 2FA password.")
            return
        except Exception as e:
            logger.error(f"Login error (OTP step) for {user_id}: {e}")
            await message.reply("❌ An error occurred. Please try /login again.")
            _login_state.pop(user_id, None)
            return

        await _finalize_login(client, message, user_id, temp_client)

    # ── Step 3: Receive 2FA password ──────────────────────────────────────────
    elif step == "2fa":
        password = message.text.strip()
        asyncio.create_task(_delete_after(message, delay=3))  # Delete password immediately

        temp_client = state.get("client")

        try:
            await temp_client.check_password(password)
        except PasswordHashInvalid:
            await message.reply("❌ Incorrect 2FA password. Please try again.")
            return
        except Exception as e:
            logger.error(f"Login error (2FA step) for {user_id}: {e}")
            await message.reply("❌ An error occurred. Please try /login again.")
            _login_state.pop(user_id, None)
            return

        await _finalize_login(client, message, user_id, temp_client)


async def _finalize_login(
    bot: Client, message: Message, user_id: int, temp_client: Client
):
    """Export session, encrypt it, save to DB, and clean up."""
    try:
        session_string = await temp_client.export_session_string()
        await save_user_session(user_id, session_string)
        _login_state.pop(user_id, None)
        await temp_client.stop()
        await message.reply(
            "✅ Login successful! You can now send Telegram post links."
        )
        logger.info(f"User {user_id} logged in successfully.")
    except Exception as e:
        logger.error(f"Failed to finalize login for {user_id}: {e}")
        await message.reply("❌ Could not save session. Please try /login again.")
        _login_state.pop(user_id, None)


async def _expire_login(user_id: int, timeout: int):
    """Cancel a stale login attempt after `timeout` seconds."""
    await asyncio.sleep(timeout)
    state = _login_state.pop(user_id, None)
    if state:
        temp_client = state.get("client")
        if temp_client:
            try:
                await temp_client.stop()
            except Exception:
                pass
        logger.info(f"Login session for user {user_id} expired after {timeout}s.")


# ── /logout ───────────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("logout"))
async def logout_cmd(client: Client, message: Message):
    user_id = message.from_user.id

    if not await is_user_logged_in(user_id):
        await message.reply("ℹ️ You are not currently logged in.")
        return

    await delete_user_session(user_id)
    await message.reply("✅ Logged out successfully. Your session has been deleted.")
    logger.info(f"User {user_id} logged out.")
