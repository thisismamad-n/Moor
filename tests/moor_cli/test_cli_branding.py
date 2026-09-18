"""Unit tests for Moor CLI visual branding, artwork, and theme standards."""

import pytest
from moor_cli.banner import MOOR_AGENT_LOGO, MOOR_ANT_HERO, MOOR_CADUCEUS
from moor_cli.skin_engine import (
    _BUILTIN_SKINS,
    get_active_skin,
    get_active_help_header,
    get_active_goodbye,
    get_active_prompt_symbol,
    set_active_skin,
)


def test_banner_artwork_branding():
    """Verify ASCII top banner and hero art contain Moor assets and zero Hermes art."""
    # Top banner must not contain old HERMES lettering
    assert "HERMES" not in MOOR_AGENT_LOGO
    assert "██╗  ██╗███████╗" not in MOOR_AGENT_LOGO
    # Must use Electric Cobalt & Cyan colors
    assert "#38bdf8" in MOOR_AGENT_LOGO or "#2563eb" in MOOR_AGENT_LOGO

    # Hero art must be the cyber-ant, not the Hermes caduceus
    assert "cyber-ant online" in MOOR_ANT_HERO
    assert "⬡" in MOOR_ANT_HERO
    assert "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⡀⠀⣀⣀⠀⢀⣀⡀" not in MOOR_ANT_HERO

    # Backward compatibility alias
    assert MOOR_CADUCEUS == MOOR_ANT_HERO


def test_skin_engine_cyber_obsidian_default():
    """Verify default skin is Cyber-Obsidian with Electric Cobalt/Cyan palette."""
    set_active_skin("default")
    skin = get_active_skin()
    assert skin.name == "default"
    assert "Cyber-Obsidian" in skin.description

    # Base palette checks
    assert skin.get_color("banner_border") == "#2563eb"
    assert skin.get_color("banner_title") == "#38bdf8"
    assert skin.get_color("banner_accent") == "#3b82f6"
    assert skin.get_color("banner_text") == "#f1f5f9"
    assert skin.get_color("status_bar_bg") == "#090b10"
    assert skin.get_color("ui_accent") == "#3b82f6"
    assert skin.get_color("ui_label") == "#06b6d4"
    assert skin.get_color("input_rule") == "#2563eb"
    assert skin.get_color("response_border") == "#2563eb"


def test_classic_gold_skin_preserved():
    """Verify the legacy gold theme is accessible via classic-gold skin."""
    assert "classic-gold" in _BUILTIN_SKINS
    gold_skin = _BUILTIN_SKINS["classic-gold"]
    assert gold_skin["colors"]["banner_title"] == "#FFD700"
    assert gold_skin["colors"]["banner_border"] == "#CD7F32"
    assert gold_skin["colors"]["banner_accent"] == "#FFBF00"


def test_persona_branding_and_zero_emojis():
    """Verify hexagonal node symbol, brutalist command header, and zero-emoji compliance."""
    set_active_skin("default")
    assert get_active_prompt_symbol().strip() == "❯"
    assert get_active_help_header() == "[?] Available Commands"
    assert get_active_goodbye() == "Session terminated."

    # Zero emojis check on all brand copy
    brand_strings = [
        MOOR_AGENT_LOGO,
        MOOR_ANT_HERO,
        get_active_help_header(),
        get_active_goodbye(),
        get_active_prompt_symbol(),
    ]
    for text in brand_strings:
        for ch in text:
            code = ord(ch)
            is_emoji = (
                (0x1F600 <= code <= 0x1F64F)
                or (0x1F300 <= code <= 0x1F5FF)
                or (0x1F680 <= code <= 0x1F6FF)
                or (0x1F900 <= code <= 0x1F9FF)
                or (0x2600 <= code <= 0x26FF and code not in (0x2621, 0x269E, 0x269F))
            )
            assert not is_emoji, f"Emoji detected in brand copy: {ch!r} (U+{code:04X})"


def test_portal_tags_legacy_aliases():
    """Verify legacy provider plugin compatibility aliases are exported."""
    from agent.portal_tags import (
        nous_portal_tags,
        nous_client_tag,
        moor_portal_tags,
        moor_client_tag,
    )

    assert nous_portal_tags() == moor_portal_tags()
    assert nous_client_tag() == moor_client_tag()
    assert any("product=moor-agent" in tag for tag in nous_portal_tags())
