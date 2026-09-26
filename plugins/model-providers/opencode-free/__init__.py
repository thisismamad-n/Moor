"""OpenCode Free provider profile: the free tier on the Zen relay (https://opencode.ai/zen/v1).

KEYLESS: the relay serves free-tier models anonymously and 401s any bearer it
doesn't recognize, so this provider never sends a credential (the runtime
resolver pins the keyless placeholder and an empty Authorization header; see
moor_cli.models.opencode_zen_free_runtime). Select via ``/model free``.
"""

from typing import Any

from agent.opencode_emulation import opencode_zen_free_headers
from agent.opencode_sanitizer import sanitize_opencode_messages
from agent.reasoning_effort import ox_alpha_reasoning_extras
from providers import register_provider
from providers.base import ProviderProfile


class OpenCodeFreeProfile(ProviderProfile):
    """OpenCode Free — keyless, with Ox Alpha reasoning controls and CLI emulation.

    Ox Alpha (x-preview-f-free) is also reachable via opencode-zen with the same wire
    contract; both profiles call ``agent.reasoning_effort.ox_alpha_reasoning_extras``.
    """

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sanitize agent markers to bypass upstream anti-agent filters."""
        return sanitize_opencode_messages(messages)

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, model: str | None = None, **context
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return ox_alpha_reasoning_extras(reasoning_config, model)

    def build_client_kwargs_extras(self, *, base_url: str | None = None) -> dict[str, Any]:
        return {"default_headers": opencode_zen_free_headers()}


opencode_free = OpenCodeFreeProfile(
    name="opencode-free", aliases=("free", "opencode_free"),
    env_vars=(),  # keyless — nothing to configure
    base_url="https://opencode.ai/zen/v1", display_name="OpenCode Free",
    description="OpenCode free models — keyless, emulated OpenCode CLI headers",
    default_headers=opencode_zen_free_headers(),
    default_aux_model="mimo-v2.5-free",
)

register_provider(opencode_free)
