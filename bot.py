import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, LOGIN_SYSTEM

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

TechVJUser = None
if not LOGIN_SYSTEM:
    if not STRING_SESSION:
        raise RuntimeError("STRING_SESSION not set.")
    TechVJUser = Client("TechVJUser", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

app = Client("techvj_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=20, sleep_threshold=30)

@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):
    await message.reply(
        "👋 Hello! I am a Save Restricted Content Bot.\n\n"
        "Use /login to log in with your Telegram account.\n"
        "Then send me a post link to save it.\n\n"
        "Use /help to see all commands."
    )

@app.on_message(filters.private & filters.command("help"))
async def help_handler(client: Client, message: Message):
    await message.reply(
        "**Commands:**\n"
        "/start - Start the bot\n"
        "/help - Show this message\n"
        "/login - Login with your Telegram account\n"
        "/logout - Logout your session\n"
        "/cancel - Cancel current task\n\n"
        "**Usage:**\n"
        "Send a Telegram post link to save it.\n"
        "Example: `https://t.me/username/123`"
    )

import TechVJ_login
import TechVJ_save
import broadcast

async def main():
    async with app:
        me = await app.get_me()
        logger.info(f"Bot started: @{me.username}")
        if TechVJUser:
            await TechVJUser.start()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
