"""OpenCode provider profiles (Zen + Go).

Both route api_mode per model in core; these profiles carry the
chat_completions reasoning translations (GLM-5.2, Kimi K2, DeepSeek, Ox Alpha).
"""

from typing import Any

from agent import reasoning_effort as re_
from agent.opencode_sanitizer import sanitize_opencode_messages
from moor_cli import __version__ as _MOOR_VERSION
from providers import register_provider
from providers.base import ProviderProfile


def opencode_zen_client_headers() -> dict[str, str]:
    """Default headers for OpenCode Zen / Go requests."""
    headers = {
        "HTTP-Referer": "https://github.com/thisismamad-n/Moor",
        "X-Title": "Moor Agent",
    }
    try:
        from agent.opencode_emulation import (
            is_opencode_emulation_enabled,
            get_emulated_user_agent,
            DEFAULT_OPENCODE_CLIENT_VALUE,
            DEFAULT_OPENCODE_PROJECT_VALUE,
        )
        if is_opencode_emulation_enabled():
            headers["User-Agent"] = get_emulated_user_agent()
            headers["x-opencode-client"] = DEFAULT_OPENCODE_CLIENT_VALUE
            headers["x-opencode-project"] = DEFAULT_OPENCODE_PROJECT_VALUE
            return headers
    except Exception:
        pass
    headers["User-Agent"] = f"MoorAgent/{_MOOR_VERSION}"
    return headers


def _flat_model_name(model: str | None) -> str:
    """Bare OpenCode model ID, tolerating aggregator prefixes."""
    return (model or "").strip().rsplit("/", 1)[-1].lower()


# Version-less DeepSeek ids that still carry the thinking/effort knobs on this wire: the retired
# ``deepseek-reasoner`` alias and the canonical ``deepseek-flash`` (2026-09 Flash refresh), for
# which the Go relay honours the same top-level ``reasoning_effort``/``thinking`` contract.
_THINKING_CAPABLE_IDS: frozenset[str] = frozenset({"deepseek-reasoner", "deepseek-flash"})


def _is_deepseek_thinking_model(model: str | None) -> bool:
    m = _flat_model_name(model)
    return (m.startswith("deepseek-v") and not m.startswith("deepseek-v3")) or m in _THINKING_CAPABLE_IDS


def _is_glm_5_2_model(model: str | None) -> bool:
    """GLM-5.2 across alias spellings (glm-5.2 / glm-5-2 / glm-5p2)."""
    m = _flat_model_name(model)
    return any(token in m for token in ("glm-5.2", "glm-5-2", "glm-5p2"))


class OpenCodeGoProfile(ProviderProfile):
    """OpenCode Go - model-specific reasoning controls and CLI emulation."""

    # The relay's default max_tokens (262144) exceeds what Xiaomi accepts for
    # mimo-v2.5-pro and 400s; keys are normalized via _flat_model_name().
    _MODEL_MAX_TOKENS: dict[str, int] = {"mimo-v2.5-pro": 131072}

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sanitize agent markers to bypass upstream anti-agent filters."""
        return sanitize_opencode_messages(messages)

    def get_max_tokens(self, model: str | None) -> int | None:
        cap = self._MODEL_MAX_TOKENS.get(_flat_model_name(model))
        return self.default_max_tokens if cap is None else cap

    def build_client_kwargs_extras(self, *, base_url: str | None = None) -> dict[str, Any]:
        return {"default_headers": opencode_zen_client_headers()}

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, model: str | None = None, **context
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if _is_glm_5_2_model(model):
            # Native reasoning_effort knob (high/max); server default when unset/disabled.
            effort = re_.requested_effort(reasoning_config)
            if effort is None or effort == "none":
                return {}, {}
            clamped = re_.clamp_effort(effort, re_.GLM52_EFFORTS, re_.GLM52_OVERRIDES)
            return {}, {"reasoning_effort": clamped if clamped in re_.GLM52_EFFORTS else "high"}
        if _flat_model_name(model).startswith("kimi-k2"):
            if not isinstance(reasoning_config, dict):
                return {}, {}
            return re_.thinking_toggle_extras(reasoning_config, re_.KIMI_K2_EFFORTS)
        if _is_deepseek_thinking_model(model):
            return re_.thinking_toggle_extras(reasoning_config, re_.DEEPSEEK_V4_EFFORTS, re_.DEEPSEEK_V4_OVERRIDES)
        return {}, {}


class OpenCodeZenProfile(ProviderProfile):
    """OpenCode Zen - model-specific reasoning controls and CLI emulation."""

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sanitize agent markers to bypass upstream anti-agent filters."""
        return sanitize_opencode_messages(messages)

    def build_client_kwargs_extras(self, *, base_url: str | None = None) -> dict[str, Any]:
        return {"default_headers": opencode_zen_client_headers()}

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, model: str | None = None, **context
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return re_.ox_alpha_reasoning_extras(reasoning_config, model)


opencode_zen = OpenCodeZenProfile(
    name="opencode-zen", aliases=("opencode", "opencode_zen", "zen"), env_vars=("OPENCODE_ZEN_API_KEY",),
    base_url="https://opencode.ai/zen/v1", default_headers=opencode_zen_client_headers(),
    default_aux_model="gemini-3-flash",
)

opencode_go = OpenCodeGoProfile(
    name="opencode-go", aliases=("opencode_go", "go", "opencode-go-sub"), env_vars=("OPENCODE_GO_API_KEY",),
    base_url="https://opencode.ai/zen/go/v1", default_headers=opencode_zen_client_headers(),
    default_aux_model="glm-5",
    supports_vision_tool_messages=False,
)

register_provider(opencode_zen)
register_provider(opencode_go)
