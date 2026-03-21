import os
import sys
import logging

logger = logging.getLogger(__name__)


def _get_required(key: str) -> str:
    """Fetch a required environment variable. Exit immediately if missing."""
    value = os.environ.get(key, "").strip()
    if not value:
        logger.critical(f"[STARTUP ERROR] Required environment variable '{key}' is not set. Exiting.")
        sys.exit(1)
    return value


def _get_bool(key: str, default: bool) -> bool:
    """Safely parse a boolean environment variable."""
    raw = os.environ.get(key, "").strip().lower()
    if raw in ("true", "1", "yes"):
        return True
    if raw in ("false", "0", "no"):
        return False
    return default


def _get_int(key: str, default: int) -> int:
    """Safely parse an integer environment variable."""
    raw = os.environ.get(key, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        logger.warning(f"[CONFIG] Invalid integer for '{key}', using default: {default}")
        return default


def _get_int_list(key: str) -> list[int]:
    """Parse a comma-separated list of integers (e.g. for ADMINS)."""
    raw = os.environ.get(key, "").strip()
    if not raw:
        logger.critical(f"[STARTUP ERROR] Required environment variable '{key}' is not set. Exiting.")
        sys.exit(1)
    try:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError:
        logger.critical(f"[STARTUP ERROR] '{key}' must be a comma-separated list of integers. Exiting.")
        sys.exit(1)


# ── Login System ──────────────────────────────────────────────────────────────
# Set LOGIN_SYSTEM=true if you want users to login with their own session.
# Set LOGIN_SYSTEM=false if you want to use a fixed STRING_SESSION instead.
LOGIN_SYSTEM: bool = _get_bool("LOGIN_SYSTEM", default=True)

# ── Telegram Credentials ──────────────────────────────────────────────────────
# Get API_ID and API_HASH from https://my.telegram.org
API_ID: int = _get_int("API_ID", default=0)
if API_ID == 0:
    logger.critical("[STARTUP ERROR] API_ID is not set or invalid. Exiting.")
    sys.exit(1)

API_HASH: str = _get_required("API_HASH")
BOT_TOKEN: str = _get_required("BOT_TOKEN")

# STRING_SESSION is required only when LOGIN_SYSTEM is False
if not LOGIN_SYSTEM:
    STRING_SESSION: str | None = _get_required("STRING_SESSION")
else:
    STRING_SESSION = None

# ── Admin & Channel ───────────────────────────────────────────────────────────
# ADMINS: comma-separated Telegram user IDs, e.g. "123456,789012"
ADMINS: list[int] = _get_int_list("ADMINS")

# CHANNEL_ID: optional channel where the bot uploads content
CHANNEL_ID: str = os.environ.get("CHANNEL_ID", "").strip()

# ── Database ──────────────────────────────────────────────────────────────────
# DB_URI: MongoDB connection string — NEVER hardcode this in code or commit it
DB_URI: str = _get_required("DB_URI")
DB_NAME: str = os.environ.get("DB_NAME", "vjsavecontentbot").strip()

# ── Rate Limiting & Behaviour ─────────────────────────────────────────────────
# WAITING_TIME: seconds to wait between requests to avoid flood bans (min: 5)
WAITING_TIME: int = max(5, _get_int("WAITING_TIME", default=15))

# ERROR_MESSAGE: whether to DM error details to the admin
ERROR_MESSAGE: bool = _get_bool("ERROR_MESSAGE", default=True)

# MAX_BATCH_SIZE: max number of posts allowed in a single range request
MAX_BATCH_SIZE: int = _get_int("MAX_BATCH_SIZE", default=50)

# MAX_CONCURRENT_USERS: soft cap on simultaneous active user tasks
MAX_CONCURRENT_USERS: int = _get_int("MAX_CONCURRENT_USERS", default=10)
