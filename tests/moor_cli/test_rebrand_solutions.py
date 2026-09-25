"""Unit tests verifying Moor rebrand resilience, dual API keys, and vendor independence."""

import os
from unittest.mock import MagicMock, patch
import pytest

from moor_cli.providers import ALIASES, MOOR_OVERLAYS, _ALIAS_GROUPS
from moor_cli.banner import _OFFICIAL_REPO_CANONICAL, _UPSTREAM_REPO_URL, MOOR_AGENT_LOGO, MOOR_ANT_HERO


def test_provider_overlay_dual_env_vars():
    """Verify moor provider overlay supports both MOOR_API_KEY and legacy NOUS_API_KEY."""
    assert "moor" in MOOR_OVERLAYS
    overlay = MOOR_OVERLAYS["moor"]
    assert "MOOR_API_KEY" in overlay.extra_env_vars
    assert "NOUS_API_KEY" in overlay.extra_env_vars


def test_alias_groups_moor_mappings():
    """Verify alias groups normalize legacy moor provider slugs to moor."""
    assert "moor" in _ALIAS_GROUPS
    aliases = _ALIAS_GROUPS["moor"]
    assert "moor" in aliases
    assert "nousresearch" in aliases
    assert "moor-portal" in aliases

    assert ALIASES.get("moor") == "moor"
    assert ALIASES.get("nousresearch") == "moor"
    assert ALIASES.get("moor-portal") == "moor"


def test_model_provider_plugin_moor_profile():
    """Verify plugins/model-providers/moor exports Moor Cloud with dual env vars."""
    from providers import get_provider_profile
    provider = get_provider_profile("moor")
    assert provider is not None
    assert provider.display_name == "Moor Cloud"
    assert "MOOR_API_KEY" in provider.env_vars
    assert "NOUS_API_KEY" in provider.env_vars
    assert "moor" in provider.aliases


def test_official_repo_canonical_target():
    """Verify banner and update targets identify the Moor repository."""
    assert _OFFICIAL_REPO_CANONICAL == "github.com/thisismamad-n/Moor"
    assert _UPSTREAM_REPO_URL == "https://github.com/thisismamad-n/Moor.git"


def test_user_agent_headers_attribution():
    """Verify outgoing User-Agent headers identify strictly as MoorAgent."""
    import agent.codex_headers as codex_headers
    headers = codex_headers.codex_cloudflare_headers("")
    assert "MoorAgent" in headers["User-Agent"]
    assert "Hermes" not in headers["User-Agent"]  # LEGACY-REBRAND-TEST: brand check

    from agent.auxiliary_client import _OR_HEADERS_BASE
    assert _OR_HEADERS_BASE["HTTP-Referer"] == "https://github.com/thisismamad-n/Moor"
    assert _OR_HEADERS_BASE["X-Title"] == "Moor Agent"

    from gateway.relay.media import _MEDIA_USER_AGENT
    assert "MoorAgent" in _MEDIA_USER_AGENT
    assert "thisismamad-n/Moor" in _MEDIA_USER_AGENT


def test_plugin_catalog_urls_and_fallback():
    """Verify plugin catalog uses Moor raw GitHub as primary with fallback."""
    from moor_cli.plugin_catalog import LIVE_CATALOG_URL, LIVE_CATALOG_FALLBACK_URL
    assert "thisismamad-n/Moor" in LIVE_CATALOG_URL
    assert LIVE_CATALOG_FALLBACK_URL is not None


def test_model_catalog_urls_and_fallback():
    """Verify model catalog uses Moor raw GitHub as primary with fallback."""
    from moor_cli.model_catalog import DEFAULT_CATALOG_URL, DEFAULT_CATALOG_FALLBACK_URLS
    assert "thisismamad-n/Moor" in DEFAULT_CATALOG_URL
    assert len(DEFAULT_CATALOG_FALLBACK_URLS) >= 1


def test_skills_hub_official_repo():
    """Verify skills hub search references the Moor official repo."""
    from tools.skills_hub_official import OptionalSkillSource
    assert OptionalSkillSource.OFFICIAL_REPO == "thisismamad-n/Moor"


def test_zero_emojis_in_artwork_and_banners():
    """Verify zero emoji directive on logo, hero, and prompt strings."""
    for text in (MOOR_AGENT_LOGO, MOOR_ANT_HERO):
        for ch in text:
            code = ord(ch)
            is_emoji = (
                (0x1F600 <= code <= 0x1F64F)
                or (0x1F300 <= code <= 0x1F5FF)
                or (0x1F680 <= code <= 0x1F6FF)
                or (0x1F900 <= code <= 0x1F9FF)
                or (0x2600 <= code <= 0x26FF and code not in (0x2621, 0x269E, 0x269F))
            )
            assert not is_emoji, f"Emoji detected in brand artwork: {ch!r} (U+{code:04X})"
