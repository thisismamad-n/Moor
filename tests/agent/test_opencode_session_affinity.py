"""x-opencode-session rides on every OpenCode request, on every transport."""

from __future__ import annotations

import pytest

from agent import auxiliary_client as aux
from agent.chat_completion_helpers import build_api_kwargs
from run_agent import AIAgent

_MSGS = [{"role": "user", "content": "hi"}]


def _agent(provider, model, base_url, api_mode=None):
    agent = AIAgent(
        api_key="test-key",
        base_url=base_url,
        model=model,
        provider=provider,
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        session_id="sess-affinity-1",
    )
    if api_mode:
        agent.api_mode = api_mode
        agent._transport = None
        agent._anthropic_base_url = base_url
    return agent


@pytest.mark.parametrize(
    "provider, model, base_url, api_mode",
    [
        ("opencode-go", "glm-5", "https://opencode.ai/zen/go/v1", None),  # chat_completions
        ("opencode-go", "gpt-5.6-luna", "https://opencode.ai/zen/go/v1", None),  # codex_responses
        ("opencode-go", "minimax-m2.7", "https://opencode.ai/zen/go/v1", "anthropic_messages"),
        ("opencode-free", "nemotron-3.5-lightning-free", "https://opencode.ai/zen/v1", None),
        ("custom", "glm-5", "https://opencode.ai/zen/go/v1", None),  # URL-only detection
    ],
)
def test_main_turn_sends_stable_session_header_on_every_transport(provider, model, base_url, api_mode):
    agent = _agent(provider, model, base_url, api_mode)
    first_kwargs = build_api_kwargs(agent, _MSGS)
    second_kwargs = build_api_kwargs(agent, _MSGS)

    first = first_kwargs["extra_headers"]["x-opencode-session"]
    second = second_kwargs["extra_headers"]["x-opencode-session"]
    assert first == second
    assert first.startswith("ses_")
    assert len(first) == 30  # "ses_" (4) + 12 hex + 14 b62 = 30 chars

    # OpenCode client emulation metadata
    assert first_kwargs["extra_headers"]["x-opencode-client"] == "desktop"
    assert first_kwargs["extra_headers"]["x-opencode-project"] == "global"
    assert "x-opencode-request" in first_kwargs["extra_headers"]
    assert first_kwargs["extra_headers"]["x-opencode-request"].startswith("msg_")

    other = _agent("openrouter", "anthropic/claude-sonnet-4.6", "https://openrouter.ai/api/v1")
    assert "x-opencode-session" not in (build_api_kwargs(other, _MSGS).get("extra_headers") or {})


def test_auxiliary_calls_share_the_main_turn_session_key():
    token = aux.set_runtime_main(
        "opencode-go", "glm-5", base_url="https://opencode.ai/zen/go/v1", session_id="sess-affinity-1"
    )
    try:
        kwargs = aux._build_call_kwargs("opencode-go", "glm-5", _MSGS, base_url="https://opencode.ai/zen/go/v1")
        session_hdr = kwargs["extra_headers"]["x-opencode-session"]
        assert session_hdr.startswith("ses_")
        assert kwargs["extra_headers"]["x-opencode-client"] == "desktop"
        assert kwargs["extra_headers"]["x-opencode-project"] == "global"
        other = aux._build_call_kwargs("openrouter", "x", _MSGS, base_url="https://openrouter.ai/api/v1")
        assert "x-opencode-session" not in (other.get("extra_headers") or {})
    finally:
        aux._RUNTIME_MAIN_CONTEXT.reset(token)
