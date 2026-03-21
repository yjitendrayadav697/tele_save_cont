"""
database/users_db.py
Secure user database layer.
- Session strings are encrypted at rest using Fernet symmetric encryption.
- The encryption key must be set via the SESSION_ENCRYPTION_KEY env variable.
- Uses motor (async MongoDB driver).
"""

import os
import sys
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.fernet import Fernet, InvalidToken

from config import DB_URI, DB_NAME

logger = logging.getLogger(__name__)

# ── Encryption setup ──────────────────────────────────────────────────────────
_raw_key = os.environ.get("SESSION_ENCRYPTION_KEY", "").strip()
if not _raw_key:
    logger.critical(
        "[STARTUP ERROR] SESSION_ENCRYPTION_KEY is not set. "
        "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )
    sys.exit(1)

try:
    _fernet = Fernet(_raw_key.encode())
except Exception:
    logger.critical("[STARTUP ERROR] SESSION_ENCRYPTION_KEY is invalid. Must be a valid Fernet key.")
    sys.exit(1)


def _encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str | None:
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt session — token invalid or key mismatch.")
        return None


# ── MongoDB connection ─────────────────────────────────────────────────────────
_mongo_client = AsyncIOMotorClient(DB_URI)
_db           = _mongo_client[DB_NAME]
_users_col    = _db["users"]


# ── Public API ─────────────────────────────────────────────────────────────────

async def add_user(user_id: int):
    """Register a user in the database (idempotent)."""
    await _users_col.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"_id": user_id, "joined": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def is_user_logged_in(user_id: int) -> bool:
    doc = await _users_col.find_one({"_id": user_id}, {"session": 1})
    return bool(doc and doc.get("session"))


async def save_user_session(user_id: int, session_string: str):
    """Encrypt and persist a user's Pyrogram session string."""
    encrypted = _encrypt(session_string)
    await _users_col.update_one(
        {"_id": user_id},
        {
            "$set": {
                "session": encrypted,
                "session_updated": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"joined": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    logger.info(f"Session saved for user {user_id}.")


async def get_user_session(user_id: int) -> str | None:
    """Retrieve and decrypt a user's session string."""
    doc = await _users_col.find_one({"_id": user_id}, {"session": 1})
    if not doc or not doc.get("session"):
        return None
    return _decrypt(doc["session"])


async def delete_user_session(user_id: int):
    """Remove a user's stored session (logout)."""
    await _users_col.update_one(
        {"_id": user_id},
        {"$unset": {"session": "", "session_updated": ""}},
    )
    logger.info(f"Session deleted for user {user_id}.")


async def get_all_users() -> list[int]:
    """Return all registered user IDs (for broadcast)."""
    cursor = _users_col.find({}, {"_id": 1})
    return [doc["_id"] async for doc in cursor]


async def get_user_count() -> int:
    return await _users_col.count_documents({})
