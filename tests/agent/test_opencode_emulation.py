"""Unit tests for OpenCode CLI emulation and agent restriction bypass."""

from __future__ import annotations

import re
import pytest

from agent.opencode_emulation import (
    OPENCODE_CLIENT_HEADER,
    OPENCODE_PROJECT_HEADER,
    OPENCODE_REQUEST_HEADER,
    OPENCODE_SESSION_HEADER,
    build_opencode_emulation_headers,
    format_opencode_session_id,
    generate_opencode_request_id,
    get_emulated_user_agent,
    is_opencode_emulation_enabled,
    is_valid_opencode_request_id,
    is_valid_opencode_session_id,
)
from agent.opencode_affinity import (
    is_opencode_target,
    merge_opencode_session_headers,
    opencode_session_headers,
)
from agent.opencode_sanitizer import (
    ANTI_AGENT_PATTERN,
    sanitize_opencode_input,
    sanitize_opencode_messages,
    sanitize_system_prompt_text,
)


# ─── Session and Request ID Wire Format Tests ───────────────────────────────


def test_session_id_format_and_stability():
    """Verify session IDs strictly conform to ses_<12hex><14base62> and are stable."""
    raw_scope = "conversation-uuid-1234-abcd"
    session_id = format_opencode_session_id(raw_scope)

    assert is_valid_opencode_session_id(session_id)
    assert session_id.startswith("ses_")
    assert len(session_id) == 30

    # Deterministic output for same scope
    assert format_opencode_session_id(raw_scope) == session_id

    # Pre-formatted valid IDs pass through unchanged
    valid_id = "ses_0123456789abCdefGhijKlmn01"
    assert format_opencode_session_id(valid_id) == valid_id


def test_request_id_format_and_uniqueness():
    """Verify request IDs strictly conform to msg_<12hex><14base62>."""
    req_id = generate_opencode_request_id()

    assert is_valid_opencode_request_id(req_id)
    assert req_id.startswith("msg_")
    assert len(req_id) == 30

    # Successive calls produce distinct IDs
    req_id_2 = generate_opencode_request_id()
    assert req_id != req_id_2

    # Deterministic generation when content_hint provided
    hint_req_1 = generate_opencode_request_id("ses_123", "Write a binary search function")
    hint_req_2 = generate_opencode_request_id("ses_123", "Write a binary search function")
    assert hint_req_1 == hint_req_2
    assert is_valid_opencode_request_id(hint_req_1)


# ─── Credential Pool Session Affinity Tests ─────────────────────────────────


def test_key_scoped_session_affinity():
    """Rotating API keys in the pool generates clean, credential-scoped session IDs."""
    scope = "session-task-99"
    key1_session = format_opencode_session_id(scope, credential_id="key-alice-1")
    key2_session = format_opencode_session_id(scope, credential_id="key-bob-2")

    assert is_valid_opencode_session_id(key1_session)
    assert is_valid_opencode_session_id(key2_session)
    # Different credentials produce different sessions for upstream cache isolation
    assert key1_session != key2_session

    # Same credential reproduces identical session ID
    assert format_opencode_session_id(scope, credential_id="key-alice-1") == key1_session


# ─── OpenCode Header Generation Tests ───────────────────────────────────────


def test_build_opencode_emulation_headers(monkeypatch):
    """Verify full suite of emulation headers including User-Agent, client, and project."""
    headers = build_opencode_emulation_headers(session_id="conv-101")

    assert headers[OPENCODE_CLIENT_HEADER] == "desktop"
    assert headers[OPENCODE_PROJECT_HEADER] == "global"
    assert headers["User-Agent"] == "opencode/1.18.31"
    assert is_valid_opencode_session_id(headers[OPENCODE_SESSION_HEADER])
    assert is_valid_opencode_request_id(headers[OPENCODE_REQUEST_HEADER])


def test_custom_user_agent_and_toggle(monkeypatch):
    """Verify User-Agent override and toggle via environment variables."""
    monkeypatch.setenv("OPENCODE_EMULATED_VERSION", "opencode/1.20.0")
    assert get_emulated_user_agent() == "opencode/1.20.0"

    headers = build_opencode_emulation_headers(session_id="conv-101")
    assert headers["User-Agent"] == "opencode/1.20.0"

    # Disable emulation
    monkeypatch.setenv("OPENCODE_EMULATE_CLIENT", "false")
    assert not is_opencode_emulation_enabled()
    headers_disabled = build_opencode_emulation_headers(session_id="conv-101")
    assert "User-Agent" not in headers_disabled


# ─── Targeted Prompt Sanitization Tests ───────────────────────────────────────


def test_targeted_system_prompt_sanitization():
    """Verify agent markers are neutralized while preserving technical instructions."""
    prompt_with_markers = (
        "<agent-identity>\n"
        "You are Moor, a powerful agentic AI coding assistant designed by DeepMind.\n"
        "</agent-identity>\n"
        "Here are your tools:\n"
        "- run_command: Run a shell command.\n"
        "- write_to_file: Write code to file.\n"
        "Please fix the bug in calculationEngine.ts."
    )

    cleaned = sanitize_system_prompt_text(prompt_with_markers)

    # Agent markers removed / sanitized
    assert "<agent-identity>" not in cleaned
    assert "</agent-identity>" not in cleaned
    assert "You are Moor" not in cleaned
    assert "powerful agentic AI coding assistant" not in cleaned

    # Tool definitions and user instructions preserved
    assert "- run_command: Run a shell command." in cleaned
    assert "- write_to_file: Write code to file." in cleaned
    assert "Please fix the bug in calculationEngine.ts." in cleaned
    assert "You are an AI software engineering assistant." in cleaned


def test_clean_prompt_left_untouched():
    """Prompts without agent markers remain completely unchanged."""
    normal_prompt = "You are a Python expert. Implement Dijkstra's shortest path algorithm."
    assert sanitize_system_prompt_text(normal_prompt) == normal_prompt


def test_sanitize_opencode_messages():
    """Sanitizes only system messages in a conversation history, leaving user/assistant untouched."""
    msgs = [
        {
            "role": "system",
            "content": "<agent-identity>You are Claude Code, Anthropic's official CLI.</agent-identity> System rules here.",
        },
        {"role": "user", "content": "You are claude code? No, I am asking a question."},
        {"role": "assistant", "content": "I will inspect your repository."},
    ]

    sanitized = sanitize_opencode_messages(msgs)

    # System message was sanitized
    assert "<agent-identity>" not in sanitized[0]["content"]
    assert "System rules here." in sanitized[0]["content"]

    # User and assistant messages were NOT modified
    assert sanitized[1]["content"] == msgs[1]["content"]
    assert sanitized[2]["content"] == msgs[2]["content"]


def test_sanitize_opencode_input_responses_api():
    """Sanitizes Responses API input structures."""
    input_items = [
        {
            "type": "message",
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "input_text": "You are Moor, a powerful agentic AI coding assistant. Tool specs follow.",
                }
            ],
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "input_text": "Fix calculation"}],
        },
    ]

    sanitized = sanitize_opencode_input(input_items)
    text = sanitized[0]["content"][0]["input_text"]
    assert "You are Moor" not in text
    assert "Tool specs follow." in text
    assert sanitized[1]["content"][0]["input_text"] == "Fix calculation"


# ─── Wire Integration & End-to-End Tests ────────────────────────────────────


def test_merge_opencode_session_headers_applies_all():
    """Verify merge_opencode_session_headers attaches emulation headers and scrubs prompts."""
    kwargs = {
        "messages": [
            {
                "role": "system",
                "content": "<agent-identity>You are Moor, a powerful AI agent.</agent-identity> Write code.",
            },
            {"role": "user", "content": "Hello"},
        ]
    }

    result = merge_opencode_session_headers(
        kwargs,
        provider="opencode-free",
        base_url="https://opencode.ai/zen/v1",
        session_id="sess-test-42",
        credential_id="cred-abc",
    )

    headers = result["extra_headers"]
    assert headers["x-opencode-client"] == "desktop"
    assert headers["x-opencode-project"] == "global"
    assert is_valid_opencode_session_id(headers["x-opencode-session"])
    assert is_valid_opencode_request_id(headers["x-opencode-request"])
    assert headers["User-Agent"] == "opencode/1.18.31"

    # Message sanitization
    sys_content = result["messages"][0]["content"]
    assert "<agent-identity>" not in sys_content
    assert "Write code." in sys_content


def test_non_opencode_targets_unaffected():
    """Non-OpenCode targets pass through untouched without extra headers or scrubbing."""
    orig_msg = "<agent-identity>You are Moor.</agent-identity>"
    kwargs = {"messages": [{"role": "system", "content": orig_msg}]}

    result = merge_opencode_session_headers(
        kwargs,
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        session_id="sess-42",
    )

    assert "extra_headers" not in result
    assert result["messages"][0]["content"] == orig_msg
