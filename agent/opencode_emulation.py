"""OpenCode CLI emulation helpers.

OpenCode's Zen/Go/Free relay enforces strict client identity checks and wire
formats:
1. User-Agent must be an official OpenCode client (>= 1.17, default: opencode/1.18.31)
   to avoid 429 rate limit walls on models such as big-pickle.
2. HTTP headers required for client session affinity and request tracking:
   - ``x-opencode-client``: "desktop"
   - ``x-opencode-project``: "global"
   - ``x-opencode-session``: strictly formatted as ``ses_<12hex><14base62>``
   - ``x-opencode-request``: strictly formatted as ``msg_<12hex><14base62>``
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import time
from typing import Mapping, Optional

# Regex formats conforming to OpenCode relay expectations
OPENCODE_SESSION_RE = re.compile(r"^ses_[0-9a-f]{12}[0-9A-Za-z]{14}$")
OPENCODE_REQUEST_RE = re.compile(r"^msg_[0-9a-f]{12}[0-9A-Za-z]{14}$")

OPENCODE_SESSION_HEADER = "x-opencode-session"
OPENCODE_REQUEST_HEADER = "x-opencode-request"
OPENCODE_CLIENT_HEADER = "x-opencode-client"
OPENCODE_PROJECT_HEADER = "x-opencode-project"

DEFAULT_OPENCODE_EMULATED_VERSION = "opencode/1.18.31"
DEFAULT_OPENCODE_CLIENT_VALUE = "desktop"
DEFAULT_OPENCODE_PROJECT_VALUE = "global"

_BASE62_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def is_opencode_emulation_enabled() -> bool:
    """Whether OpenCode client emulation is enabled. Defaults to True."""
    val = os.environ.get("OPENCODE_EMULATE_CLIENT", "true").strip().lower()
    return val not in ("false", "0", "no", "off")


def get_emulated_user_agent() -> str:
    """Return the configured or default emulated OpenCode User-Agent string."""
    ua = os.environ.get("OPENCODE_EMULATED_VERSION", "").strip()
    return ua if ua else DEFAULT_OPENCODE_EMULATED_VERSION


def is_valid_opencode_session_id(val: Optional[str]) -> bool:
    """True if *val* matches the canonical ``ses_<12hex><14base62>`` format."""
    return bool(isinstance(val, str) and OPENCODE_SESSION_RE.match(val.strip()))


def is_valid_opencode_request_id(val: Optional[str]) -> bool:
    """True if *val* matches the canonical ``msg_<12hex><14base62>`` format."""
    return bool(isinstance(val, str) and OPENCODE_REQUEST_RE.match(val.strip()))


def format_opencode_session_id(
    scope: Optional[str],
    credential_id: Optional[str] = None,
) -> str:
    """Deterministically generate or pass through an OpenCode session ID.

    If *scope* already matches ``^ses_[0-9a-f]{12}[0-9A-Za-z]{14}$``, it is preserved.
    Otherwise, derives a deterministic 12-hex + 14-base62 ID from
    ``opencode\\0<credential_id>\\0<scope>``.
    """
    raw = str(scope or "").strip()
    if is_valid_opencode_session_id(raw):
        return raw

    cred = str(credential_id or "generic").strip()
    seed = f"opencode\0{cred}\0{raw}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()

    hex_part = digest[:6].hex()  # 6 bytes -> 12 hex digits
    b62_part = "".join(_BASE62_ALPHABET[b % 62] for b in digest[6:20])  # 14 base62 chars

    return f"ses_{hex_part}{b62_part}"


def generate_opencode_request_id(
    session_id: Optional[str] = None,
    content_hint: Optional[str] = None,
) -> str:
    """Generate a format-compliant OpenCode request ID: ``msg_<12hex><14base62>``.

    When *content_hint* is provided, derives deterministically from
    ``opencode-req\\0<session_id>\\0<content_hint>``. Otherwise generates a unique
    timestamp-shifted request ID.
    """
    if content_hint:
        hint_str = content_hint[-600:] if len(content_hint) > 600 else content_hint
        seed = f"opencode-req\0{session_id or ''}\0{hint_str}".encode("utf-8")
        digest = hashlib.sha256(seed).digest()
        hex_part = digest[:6].hex()
        b62_part = "".join(_BASE62_ALPHABET[b % 62] for b in digest[6:20])
        return f"msg_{hex_part}{b62_part}"

    now_ms = int(time.time() * 1000)
    ts_bytes = (now_ms << 12).to_bytes(8, byteorder="big", signed=False)[2:8]
    hex_part = ts_bytes.hex()
    random_bytes = secrets.token_bytes(14)
    b62_part = "".join(_BASE62_ALPHABET[b % 62] for b in random_bytes)
    return f"msg_{hex_part}{b62_part}"


def build_opencode_emulation_headers(
    session_id: Optional[str] = None,
    credential_id: Optional[str] = None,
    existing_headers: Optional[Mapping[str, str]] = None,
    content_hint: Optional[str] = None,
) -> dict[str, str]:
    """Build all HTTP headers needed to emulate the OpenCode CLI."""
    headers: dict[str, str] = {}
    normalized_existing: dict[str, str] = {}
    if existing_headers:
        for k, v in existing_headers.items():
            normalized_existing[k.lower()] = str(v)

    # 1. Session ID
    existing_session = normalized_existing.get(OPENCODE_SESSION_HEADER)
    session_key = format_opencode_session_id(existing_session or session_id, credential_id)
    headers[OPENCODE_SESSION_HEADER] = session_key

    # 2. Request ID
    existing_req = normalized_existing.get(OPENCODE_REQUEST_HEADER)
    if existing_req and is_valid_opencode_request_id(existing_req):
        headers[OPENCODE_REQUEST_HEADER] = existing_req
    else:
        headers[OPENCODE_REQUEST_HEADER] = generate_opencode_request_id(session_key, content_hint)

    # 3. Client & Project metadata
    headers[OPENCODE_CLIENT_HEADER] = (
        normalized_existing.get(OPENCODE_CLIENT_HEADER) or DEFAULT_OPENCODE_CLIENT_VALUE
    )
    headers[OPENCODE_PROJECT_HEADER] = (
        normalized_existing.get(OPENCODE_PROJECT_HEADER) or DEFAULT_OPENCODE_PROJECT_VALUE
    )

    # 4. User-Agent
    if is_opencode_emulation_enabled():
        headers["User-Agent"] = get_emulated_user_agent()

    return headers


def opencode_zen_free_headers() -> dict[str, str]:
    """Client default_headers for anonymous Zen free-tier requests.

    Authorization: "" overrides the OpenAI SDK's Bearer <api_key> so the placeholder
    never reaches the wire (the relay 401s any unknown bearer). Emulation headers
    match the OpenCode CLI wire profile.
    """
    base: dict[str, str] = {
        "Authorization": "",
        "HTTP-Referer": "https://github.com/thisismamad-n/Moor",
        "X-Title": "Moor Agent",
    }
    if is_opencode_emulation_enabled():
        base["User-Agent"] = get_emulated_user_agent()
        base[OPENCODE_CLIENT_HEADER] = DEFAULT_OPENCODE_CLIENT_VALUE
        base[OPENCODE_PROJECT_HEADER] = DEFAULT_OPENCODE_PROJECT_VALUE
    else:
        try:
            from moor_cli import __version__ as _v
        except Exception:
            _v = "0"
        base["User-Agent"] = f"MoorAgent/{_v}"
    return base

