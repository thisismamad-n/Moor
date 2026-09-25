"""``x-opencode-*`` — OpenCode relay session-affinity and client emulation headers.

OpenCode (opencode.ai Zen/Go/free relay) pins requests that share an
``x-opencode-session`` value to the same upstream backend, which is what
keeps its prompt cache warm across the turns of one conversation.

The OpenCode wire protocol expects:
1. ``x-opencode-session``: strictly formatted as ``ses_<12hex><14base62>``
2. ``x-opencode-request``: strictly formatted as ``msg_<12hex><14base62>``
3. ``x-opencode-client``: "desktop"
4. ``x-opencode-project``: "global"
5. ``User-Agent``: "opencode/1.18.31" (when emulation is active)

Every OpenCode request — main turn on any transport, auxiliary calls
(compression, titles, vision, MoA) — goes through :func:`opencode_session_headers`
so headers and prompt sanitization remain consistent across code paths.
"""

from __future__ import annotations

from typing import Any, Optional

from agent.opencode_emulation import (
    OPENCODE_CLIENT_HEADER,
    OPENCODE_PROJECT_HEADER,
    OPENCODE_REQUEST_HEADER,
    OPENCODE_SESSION_HEADER,
    build_opencode_emulation_headers,
    format_opencode_session_id,
    is_valid_opencode_session_id,
)
from agent.opencode_sanitizer import (
    sanitize_opencode_input,
    sanitize_opencode_messages,
)


def is_opencode_target(provider: Optional[str], base_url: Optional[str]) -> bool:
    """True when *provider* or *base_url* addresses the OpenCode relay.

    Matches the built-in opencode-zen/go/free providers, custom
    ``opencode-<family>-*`` providers, and any base_url hosted on opencode.ai.
    """
    try:
        from moor_cli.models import opencode_provider_family

        if opencode_provider_family(provider) is not None:
            return True
    except Exception:
        pass
    try:
        from agent.anthropic_endpoints import _is_opencode_endpoint

        return _is_opencode_endpoint(str(base_url or ""))
    except Exception:
        return False


def _extract_last_user_message_hint(kwargs: dict[str, Any]) -> Optional[str]:
    """Extract up to 600 chars of the latest user message as a request hash hint."""
    messages = kwargs.get("messages")
    if isinstance(messages, list):
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()[-600:]
                if isinstance(content, list):
                    texts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") in ("text", "input_text"):
                            t = part.get("text") or part.get("input_text") or ""
                            if isinstance(t, str) and t.strip():
                                texts.append(t.strip())
                    if texts:
                        return " ".join(texts)[-600:]

    input_items = kwargs.get("input")
    if isinstance(input_items, list):
        for item in reversed(input_items):
            if isinstance(item, dict) and item.get("role") == "user":
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()[-600:]
                if isinstance(content, list):
                    texts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") in ("text", "input_text"):
                            t = part.get("text") or part.get("input_text") or ""
                            if isinstance(t, str) and t.strip():
                                texts.append(t.strip())
                    if texts:
                        return " ".join(texts)[-600:]
    return None


def opencode_session_headers(
    provider: Optional[str],
    base_url: Optional[str],
    session_id: Optional[str] = None,
    credential_id: Optional[str] = None,
    content_hint: Optional[str] = None,
    existing_headers: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Return OpenCode emulation and affinity headers for OpenCode targets, else ``{}``."""
    if not is_opencode_target(provider, base_url):
        return {}

    try:
        from agent.portal_tags import get_affinity_scope, get_conversation_context
        from agent.transports.codex import _cache_scope_from_session_id

        raw_scope = _cache_scope_from_session_id(
            get_affinity_scope() or get_conversation_context() or session_id
        )
    except Exception:
        raw_scope = str(session_id or "")

    return build_opencode_emulation_headers(
        session_id=raw_scope,
        credential_id=credential_id,
        existing_headers=existing_headers,
        content_hint=content_hint,
    )


def merge_opencode_session_headers(
    kwargs: dict[str, Any],
    provider: Optional[str],
    base_url: Optional[str],
    session_id: Optional[str] = None,
    credential_id: Optional[str] = None,
) -> dict[str, Any]:
    """Merge OpenCode emulation headers into ``kwargs['extra_headers']`` and sanitize prompts.

    Existing headers take precedence where explicitly pinned. Prompts (messages / input)
    have external agent signatures neutralized to prevent upstream rejection.
    Non-OpenCode targets are left untouched.
    """
    if not is_opencode_target(provider, base_url):
        return kwargs

    content_hint = _extract_last_user_message_hint(kwargs)
    existing = kwargs.get("extra_headers")
    headers = opencode_session_headers(
        provider,
        base_url,
        session_id=session_id,
        credential_id=credential_id,
        content_hint=content_hint,
        existing_headers=existing if isinstance(existing, dict) else None,
    )

    if headers:
        merged = dict(existing) if isinstance(existing, dict) else {}
        for key, value in headers.items():
            merged.setdefault(key, value)
        kwargs["extra_headers"] = merged

    # Targeted prompt sanitization for OpenCode targets
    if "messages" in kwargs and isinstance(kwargs["messages"], list):
        kwargs["messages"] = sanitize_opencode_messages(kwargs["messages"])

    if "input" in kwargs and isinstance(kwargs["input"], list):
        kwargs["input"] = sanitize_opencode_input(kwargs["input"])

    return kwargs
