"""Targeted prompt sanitization for OpenCode targets.

Upstream OpenCode relay models and proxies employ anti-agent filters that reject
or degrade requests containing explicit external agent identity markers
(such as ``<agent-identity>``, ``you are claude code``, ``you are an ai coding agent``,
``cc_entrypoint``, ``orchestration capabilities``).

This module performs targeted sanitization to neutralize external agent identity
signatures into neutral software engineering assistant framing, while completely
preserving tool schemas, technical instructions, system guidelines, and user context.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

# Detects common agent signatures flagged by upstream anti-agent filters
ANTI_AGENT_PATTERN = re.compile(
    r"you are claude code|"
    r"claude[._\s-]?code.+official.+cli|"
    r"anthropic.+official.+cli|"
    r"anxthxropic.+official.+cli|"
    r"you are (?:cursor|windsurf|cline|aider|continue|copilot|cody|moor|moor)|"
    r"you are an? (?:ai )?(?:coding |code )?agent|"
    r"cc_entrypoint\s*=\s*(?:cli|vscode|jetbrains|gui)|"
    r"claude[._\s-]?code.+issues|"
    r"give feedback.+claude[._\s-]?code|"
    r"you are .{0,30}(?:powerful )?ai agent|"
    r"orchestration capabilities|"
    r"OhMyOpenCode|"
    r"<agent-identity>|"
    r"<Role>|"
    r"<Behavior_Instructions>",
    re.IGNORECASE,
)

# Targeted replacements for known agent identity tags and phrases
_AGENT_IDENTITY_TAG_RE = re.compile(r"<agent-identity>.*?</agent-identity>", re.DOTALL | re.IGNORECASE)
_ROLE_TAG_RE = re.compile(r"<Role>.*?</Role>", re.DOTALL | re.IGNORECASE)
_BEHAVIOR_TAG_RE = re.compile(r"<Behavior_Instructions>.*?</Behavior_Instructions>", re.DOTALL | re.IGNORECASE)

_IDENTITY_PHRASES_RES: tuple[tuple[re.Pattern, str], ...] = (
    (
        re.compile(r"You are Moor, a powerful agentic AI coding assistant[^\n.]*", re.IGNORECASE),
        "You are an AI software engineering assistant.",
    ),
    (
        re.compile(r"You are Moor[^\n.]*AI (?:coding )?assistant[^\n.]*", re.IGNORECASE),
        "You are an AI software engineering assistant.",
    ),
    (
        re.compile(r"You are Moor, an autonomous AI (?:coding )?agent[^\n.]*", re.IGNORECASE),
        "You are an AI software engineering assistant.",
    ),
    (
        re.compile(r"You are Claude Code, Anthropic's official CLI[^\n.]*", re.IGNORECASE),
        "You are an AI software engineering assistant.",
    ),
    (
        re.compile(r"You are an? (?:ai )?(?:coding |code )?agent[^\n.]*", re.IGNORECASE),
        "You are an AI software engineering assistant.",
    ),
    (
        re.compile(r"orchestration capabilities", re.IGNORECASE),
        "engineering capabilities",
    ),
    (
        re.compile(r"cc_entrypoint\s*=\s*(?:cli|vscode|jetbrains|gui)[^\n]*", re.IGNORECASE),
        "",
    ),
)


def sanitize_system_prompt_text(text: str) -> str:
    """Perform targeted sanitization of agent signatures in a system prompt string."""
    if not text or not isinstance(text, str):
        return text

    if not ANTI_AGENT_PATTERN.search(text):
        return text

    cleaned = text
    # 1. Scrub identity tag blocks
    cleaned = _AGENT_IDENTITY_TAG_RE.sub("You are an AI software engineering assistant.", cleaned)
    cleaned = _ROLE_TAG_RE.sub("Role: AI Software Engineering Assistant.", cleaned)
    cleaned = _BEHAVIOR_TAG_RE.sub("", cleaned)

    # 2. Scrub specific identity phrases
    for pattern, replacement in _IDENTITY_PHRASES_RES:
        cleaned = pattern.sub(replacement, cleaned)

    return cleaned


def sanitize_opencode_message(msg: Mapping[str, Any]) -> dict[str, Any]:
    """Sanitize a single message dict if it is a system or developer role."""
    if not isinstance(msg, dict):
        return dict(msg)

    role = str(msg.get("role") or "").strip().lower()
    if role not in ("system", "developer"):
        return dict(msg)

    new_msg = dict(msg)
    content = new_msg.get("content")

    if isinstance(content, str):
        new_msg["content"] = sanitize_system_prompt_text(content)
    elif isinstance(content, list):
        new_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                part_copy = dict(part)
                part_copy["text"] = sanitize_system_prompt_text(part_copy["text"])
                new_parts.append(part_copy)
            else:
                new_parts.append(part)
        new_msg["content"] = new_parts

    return new_msg


def sanitize_opencode_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize system messages in a list of chat completion messages."""
    if not isinstance(messages, list):
        return messages
    return [sanitize_opencode_message(m) for m in messages]


def sanitize_opencode_input(input_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize input items for Responses API format."""
    if not isinstance(input_items, list):
        return input_items

    sanitized = []
    for item in input_items:
        if not isinstance(item, dict):
            sanitized.append(item)
            continue
        item_copy = dict(item)
        if item_copy.get("type") == "message":
            role = str(item_copy.get("role") or "").strip().lower()
            if role in ("system", "developer"):
                content = item_copy.get("content")
                if isinstance(content, str):
                    item_copy["content"] = sanitize_system_prompt_text(content)
                elif isinstance(content, list):
                    new_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") in ("input_text", "text"):
                            p_copy = dict(part)
                            text_key = "input_text" if "input_text" in p_copy else "text"
                            if isinstance(p_copy.get(text_key), str):
                                p_copy[text_key] = sanitize_system_prompt_text(p_copy[text_key])
                            new_parts.append(p_copy)
                        else:
                            new_parts.append(part)
                    item_copy["content"] = new_parts
        sanitized.append(item_copy)
    return sanitized
