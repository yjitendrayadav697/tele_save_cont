import logging
import asyncio
from pyrogram import Client
from config import (
    API_ID, API_HASH, BOT_TOKEN,
    STRING_SESSION, LOGIN_SYSTEM
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── User client (only when LOGIN_SYSTEM is disabled) ──────────────────────────
TechVJUser: Client | None = None

if not LOGIN_SYSTEM:
    if not STRING_SESSION:
        raise RuntimeError("LOGIN_SYSTEM is False but STRING_SESSION is not set.")
    TechVJUser = Client(
        "TechVJUser",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=STRING_SESSION,
    )


# ── Bot client ────────────────────────────────────────────────────────────────
class Bot(Client):
    def __init__(self):
        super().__init__(
            "techvj_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="TechVJ"),
            # Reduced from 150 → 20 to limit flood risk and resource abuse
            workers=20,
            # Give Telegram more breathing room before raising flood errors
            sleep_threshold=30,
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        logger.info(f"Bot started: @{me.username} (ID: {me.id})")

        # Start the user client alongside the bot if needed
        if TechVJUser is not None:
            await TechVJUser.start()
            user_me = await TechVJUser.get_me()
            logger.info(f"User client started: @{user_me.username} (ID: {user_me.id})")

    async def stop(self, *args):
        if TechVJUser is not None:
            try:
                await TechVJUser.stop()
                logger.info("User client stopped.")
            except Exception as e:
                logger.warning(f"Error stopping user client: {e}")
        await super().stop()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    bot = Bot()
    bot.run()
