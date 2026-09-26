"""Unit tests for OpenCode free-tier fingerprint cloaking, tool aliasing, and error classification.

Mirrors and validates the OpenCode fingerprinting specifications from 9router:
- Injects the lowercase quartet ('bash', 'glob', 'grep', 'read')
- Canonicalizes case variants and removes duplicate quartet declarations
- Preserves caller tool names in responses via reverse unaliasing
- Strips prior reasoning items for multi-turn Responses API calls
- Correctly classifies FreeTierError as upstream blocked rather than auth failure
"""

from __future__ import annotations

from typing import Any
import pytest

from agent.error_classifier import classify_api_error, FailoverReason
from agent.opencode_fingerprint import (
    OPENCODE_FINGERPRINT_TOOLS,
    append_missing_fingerprint_tools,
    apply_fingerprint_tools,
    conceal_fingerprint_tool_names,
    fingerprint_tool_key,
    restore_tool_names,
    retarget_tool_choice,
    strip_prior_reasoning_items,
    tool_name_of,
)
from agent.transports.types import ToolCall


CC_TOOLS = ["Task", "Bash", "Glob", "Grep", "Read", "Edit", "Write", "WebFetch"]


def _flat(names: list[str]) -> list[dict[str, Any]]:
    return [{"type": "function", "name": n} for n in names]


def _chat(names: list[str]) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": n}} for n in names]


class TestFingerprintToolKey:
    def test_canonical_quartet_members(self) -> None:
        assert fingerprint_tool_key("bash") == "bash"
        assert fingerprint_tool_key("Bash") == "bash"
        assert fingerprint_tool_key(" BASH ") == "bash"
        assert fingerprint_tool_key("glob") == "glob"
        assert fingerprint_tool_key("GLOB") == "glob"
        assert fingerprint_tool_key("grep") == "grep"
        assert fingerprint_tool_key("Read") == "read"

    def test_non_quartet_tools(self) -> None:
        assert fingerprint_tool_key("Edit") == ""
        assert fingerprint_tool_key("Write") == ""
        assert fingerprint_tool_key("terminal") == ""
        assert fingerprint_tool_key(None) == ""
        assert fingerprint_tool_key(123) == ""
        assert fingerprint_tool_key("") == ""


class TestToolNameOf:
    def test_flat_shape(self) -> None:
        assert tool_name_of({"name": "bash"}) == "bash"
        assert tool_name_of({"name": " Bash "}) == "Bash"

    def test_chat_shape(self) -> None:
        assert tool_name_of({"function": {"name": "read"}}) == "read"

    def test_invalid_shapes(self) -> None:
        assert tool_name_of({}) == ""
        assert tool_name_of(None) == ""
        assert tool_name_of("string") == ""


class TestConcealFingerprintToolNames:
    def test_renames_capitalized_quartet_members(self) -> None:
        tools = _flat(CC_TOOLS)
        canonicalized, rename_map = conceal_fingerprint_tool_names(tools)
        names = [t["name"] for t in canonicalized]

        assert "bash" in names
        assert "Bash" not in names
        assert "glob" in names
        assert "grep" in names
        assert "read" in names
        assert "Edit" in names  # non-quartet untouched
        assert rename_map.get("bash") == "Bash"
        assert rename_map.get("read") == "Read"

    def test_removes_quartet_duplicates(self) -> None:
        tools = _flat(["Bash", "bash", "Glob", "grep", "Read", "Foo", "foo"])
        canonicalized, rename_map = conceal_fingerprint_tool_names(tools)
        names = [t["name"] for t in canonicalized]

        assert names.count("bash") == 1
        assert "Foo" in names
        assert "foo" in names  # non-quartet case variants preserved

    def test_nested_chat_format(self) -> None:
        tools = _chat(["Bash", "Read", "CustomTool"])
        canonicalized, rename_map = conceal_fingerprint_tool_names(tools)
        fn_names = [t["function"]["name"] for t in canonicalized]

        assert "bash" in fn_names
        assert "read" in fn_names
        assert "CustomTool" in fn_names
        assert rename_map["bash"] == "Bash"
        assert rename_map["read"] == "Read"


class TestAppendMissingFingerprintTools:
    def test_flat_appends_only_missing(self) -> None:
        tools = _flat(["bash", "read"])
        result = append_missing_fingerprint_tools(tools, flat=True)
        names = [t["name"] for t in result]

        assert set(names) == {"bash", "read", "glob", "grep"}
        for t in result:
            if t["name"] in ("glob", "grep"):
                assert "currently unavailable" in t["description"]

    def test_chat_appends_only_missing(self) -> None:
        tools = _chat(["bash"])
        result = append_missing_fingerprint_tools(tools, flat=False)
        names = [t["function"]["name"] for t in result]

        assert set(names) == {"bash", "glob", "grep", "read"}


class TestRetargetToolChoice:
    def test_flat_tool_choice(self) -> None:
        choice = {"type": "function", "name": "Bash"}
        retargeted = retarget_tool_choice(choice, {"bash": "Bash"})
        assert retargeted["name"] == "bash"

    def test_chat_tool_choice(self) -> None:
        choice = {"type": "function", "function": {"name": "Read"}}
        retargeted = retarget_tool_choice(choice, {"read": "Read"})
        assert retargeted["function"]["name"] == "read"


class TestApplyFingerprintTools:
    def test_flat_empty_tools(self) -> None:
        final_tools, choice, rename_map = apply_fingerprint_tools([], flat=True)
        names = [t["name"] for t in final_tools]
        assert set(names) == set(OPENCODE_FINGERPRINT_TOOLS)
        assert choice == "auto"

    def test_chat_empty_tools(self) -> None:
        final_tools, choice, rename_map = apply_fingerprint_tools([], flat=False)
        names = [t["function"]["name"] for t in final_tools]
        assert set(names) == set(OPENCODE_FINGERPRINT_TOOLS)
        assert choice == "none"

    def test_chat_with_existing_tools(self) -> None:
        tools = _chat(["Bash", "Custom"])
        final_tools, choice, rename_map = apply_fingerprint_tools(tools, flat=False)
        names = [t["function"]["name"] for t in final_tools]
        assert "bash" in names
        assert "Custom" in names
        assert "glob" in names
        assert "grep" in names
        assert "read" in names
        assert choice is None  # preserved caller's unset choice


class TestRestoreToolNames:
    def test_tool_call_object(self) -> None:
        tc = ToolCall(id="call_1", name="bash", arguments="{}")
        restored = restore_tool_names(tc, {"bash": "Bash"})
        assert restored.name == "Bash"

    def test_responses_output_dict(self) -> None:
        payload = {
            "output": [
                {"type": "function_call", "name": "bash", "call_id": "c1"},
                {"type": "function_call", "name": "other", "call_id": "c2"},
            ]
        }
        restored = restore_tool_names(payload, {"bash": "Bash"})
        assert restored["output"][0]["name"] == "Bash"
        assert restored["output"][1]["name"] == "other"

    def test_responses_sse_item(self) -> None:
        payload = {"item": {"type": "function_call", "name": "read", "call_id": "c1"}}
        restored = restore_tool_names(payload, {"read": "Read"})
        assert restored["item"]["name"] == "Read"

    def test_chat_completions_choices(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "grep", "arguments": "{}"}}
                        ]
                    }
                }
            ]
        }
        restored = restore_tool_names(payload, {"grep": "Grep"})
        assert restored["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "Grep"


class TestStripPriorReasoningItems:
    def test_strips_reasoning_items_and_encrypted_content(self) -> None:
        items = [
            {"role": "user", "content": "hello"},
            {"type": "reasoning", "summary": "internal thought"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "answer"},
                    {"type": "reasoning", "summary": "nested thought"},
                ],
                "encrypted_content": "enc_secret_key_token",
            },
        ]
        cleaned = strip_prior_reasoning_items(items)

        assert len(cleaned) == 2
        assert cleaned[0]["role"] == "user"
        assert cleaned[1]["role"] == "assistant"
        assert "encrypted_content" not in cleaned[1]
        assert len(cleaned[1]["content"]) == 1
        assert cleaned[1]["content"][0]["type"] == "text"


class MockHttpError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


class TestErrorClassification:
    def test_opencode_free_tier_error_classified_as_upstream_blocked(self) -> None:
        err = MockHttpError(
            "HTTP 403: Error from provider (Console): OpenCode's free tier can only be used from within OpenCode",
            status_code=403,
        )
        verdict = classify_api_error(err, provider="opencode-free")
        assert verdict.reason == FailoverReason.upstream_blocked
        assert verdict.should_fallback is True

    def test_freetiererror_body_classified_as_upstream_blocked(self) -> None:
        err = MockHttpError('{"type":"error","error":{"type":"FreeTierError","message":"Forbidden"}}', status_code=403)
        verdict = classify_api_error(err, provider="opencode-free")
        assert verdict.reason == FailoverReason.upstream_blocked


class TestTransportIntegration:
    def test_codex_transport_fingerprints_opencode(self) -> None:
        from agent.transports.codex import ResponsesApiTransport

        transport = ResponsesApiTransport()
        kwargs = transport.build_kwargs(
            model="muse-spark-1.3-contributor-free",
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "name": "Bash"}],
            provider="opencode-free",
            base_url="https://opencode.ai/zen/v1",
        )
        tool_names = [t["name"] for t in kwargs.get("tools", [])]
        assert "bash" in tool_names
        assert "glob" in tool_names
        assert "grep" in tool_names
        assert "read" in tool_names
        assert "Bash" not in tool_names
        assert kwargs.get("tool_choice") == "auto"

    def test_chat_transport_fingerprints_opencode_empty_tools(self) -> None:
        from agent.transports.chat_completions import ChatCompletionsTransport

        transport = ChatCompletionsTransport()
        kwargs = transport.build_kwargs(
            model="mimo-v2.5-free",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            provider_name="opencode-free",
            base_url="https://opencode.ai/zen/v1",
        )
        tool_names = [t["function"]["name"] for t in kwargs.get("tools", [])]
        assert set(tool_names) == set(OPENCODE_FINGERPRINT_TOOLS)
        assert kwargs.get("tool_choice") == "none"
