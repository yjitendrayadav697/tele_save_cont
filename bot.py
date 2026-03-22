import logging
import asyncio
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, LOGIN_SYSTEM

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

TechVJUser = None
if not LOGIN_SYSTEM:
    if not STRING_SESSION:
        raise RuntimeError("STRING_SESSION not set.")
    TechVJUser = Client("TechVJUser", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

app = Client("techvj_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=20, sleep_threshold=30)

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
