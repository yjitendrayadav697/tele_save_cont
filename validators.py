"""
validators.py
Strict input validation for Telegram post links.
Prevents malformed or malicious links from reaching the core logic.
"""

import re
from dataclasses import dataclass
from typing import Optional

# Matches standard public links:  https://t.me/username/123
# Matches private links:          https://t.me/c/1234567890/123
# Matches bot links:              https://t.me/b/botusername/123
# All support optional range:     .../100-200
_LINK_RE = re.compile(
    r"^https://t\.me/"
    r"(?:(?P<type>c|b)/)?"           # optional c/ or b/ prefix
    r"(?P<chat>[\w\-]+)"             # username or numeric chat id
    r"/(?P<start>\d+)"               # start message id
    r"(?:\s*[-–]\s*(?P<end>\d+))?$"  # optional end id for range
)

# Hard cap: no more than MAX_BATCH posts per request
MAX_BATCH = 50


@dataclass
class ParsedLink:
    raw: str
    chat: str
    start_id: int
    end_id: int          # equals start_id for single posts
    is_private: bool     # t.me/c/...
    is_bot: bool         # t.me/b/...


def validate_link(text: str) -> tuple[Optional[ParsedLink], Optional[str]]:
    """
    Parse and validate a Telegram post link.
    Returns (ParsedLink, None) on success or (None, error_message) on failure.
    """
    text = text.strip()

    # Basic sanity checks
    if not text.startswith("https://t.me/"):
        return None, "Invalid link. Must start with `https://t.me/`."

    if len(text) > 200:
        return None, "Link is too long."

    match = _LINK_RE.match(text)
    if not match:
        return None, (
            "Could not parse link. Expected formats:\n"
            "• `https://t.me/username/123`\n"
            "• `https://t.me/c/chatid/123`\n"
            "• `https://t.me/b/botusername/123`\n"
            "• `https://t.me/username/100-200` (range)"
        )

    link_type = match.group("type")   # "c", "b", or None
    chat      = match.group("chat")
    start_id  = int(match.group("start"))
    end_raw   = match.group("end")
    end_id    = int(end_raw) if end_raw else start_id

    # Sanity-check message IDs
    if start_id <= 0 or end_id <= 0:
        return None, "Message IDs must be positive integers."

    if end_id < start_id:
        start_id, end_id = end_id, start_id   # swap silently

    batch_size = end_id - start_id + 1
    if batch_size > MAX_BATCH:
        return None, (
            f"Batch size too large ({batch_size}). "
            f"Maximum allowed is {MAX_BATCH} posts per request."
        )

    return ParsedLink(
        raw=text,
        chat=chat,
        start_id=start_id,
        end_id=end_id,
        is_private=(link_type == "c"),
        is_bot=(link_type == "b"),
    ), None
