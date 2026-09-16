"""Model pickers under a Moor free-tier identity.

A guest identity carrying inference shows one row, "Moor · free tier", with the single model
``moor/welcome``; the same guest with ``moor.guest: false`` shows no Moor row at all. The rule lives
in one helper (``_free_tier_moor_row``) and this file exercises it through the real row builders
against a temp ``MOOR_HOME`` with the network catalog fetch stubbed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from moor_cli.auth import _save_auth_store

GUEST_STATE = {
    "auth_method": "anonymous",
    "account_tier": "anonymous",
    "anon_token": "anon_t",
    "access_token": "aaa.bbb.ccc",
    "expires_at": "2030-01-01T00:00:00+00:00",
    "inference_base_url": "https://welcome-api.nousresearch.com/v1",
}


@pytest.fixture
def guest_home(monkeypatch, tmp_path):
    """Seed a guest identity as the only Moor state and keep every row builder offline."""
    monkeypatch.setenv("MOOR_SHARED_AUTH_DIR", str(tmp_path / "shared-store"))
    monkeypatch.setenv("MOOR_GUEST_ONBOARDING", "1")
    for var in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "NOUS_API_KEY", "LM_API_KEY", "LM_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    _save_auth_store({"active_provider": "moor", "providers": {"moor": dict(GUEST_STATE)}})

    # No network from any lap: models.dev, the Portal catalog, and Ollama Cloud all stubbed.
    from agent import models_dev
    from moor_cli import models as models_mod
    from moor_cli import model_switch_providers as msp
    monkeypatch.setattr(models_dev, "fetch_models_dev", lambda *a, **k: {})
    monkeypatch.setattr(models_mod, "get_curated_moor_model_ids", lambda *a, **k: ["anthropic/claude-x", "openai/gpt-y"])
    monkeypatch.setattr(models_mod, "fetch_ollama_cloud_models", lambda *a, **k: [])
    monkeypatch.setattr(msp, "_moor_picker_model_ids", lambda *a, **k: pytest.fail("guest must not fetch the Portal catalog"))
    return Path(os.environ["MOOR_HOME"])


def _write_config(monkeypatch, home: Path, text: str) -> None:
    (home / "config.yaml").write_text(text)
    from moor_cli import config as cfg_mod
    for attr in ("_config_cache", "_cached_config"):
        if hasattr(cfg_mod, attr):
            monkeypatch.setattr(cfg_mod, attr, None, raising=False)


def _moor_rows(rows):
    return [r for r in rows if str(r.get("slug", "")).lower() == "moor"]


def _cli_moor_rows(config):
    from moor_cli.main_provider_setup import _build_provider_picker_rows
    ordered, _ = _build_provider_picker_rows(config, "moor", {}, {})
    return [(key, label) for key, label, _members in ordered if key == "moor"]


def test_guest_identity_shows_free_tier_row_with_only_welcome_model(guest_home, monkeypatch):
    from moor_cli.model_switch_providers import list_picker_providers
    rows = _moor_rows(list_picker_providers("moor", "", None, None, 50, "moor/welcome"))
    assert len(rows) == 1
    row = rows[0]
    assert "free tier" in row["name"]
    assert row["models"] == ["moor/welcome"]
    assert row["total_models"] == 1
    rendered = repr(row).lower()
    assert "guest" not in rendered and "anonymous" not in rendered

    # The `moor model` provider picker applies the same rule from the same helper.
    cli_rows = _cli_moor_rows({})
    assert len(cli_rows) == 1
    assert "free tier" in cli_rows[0][1]
    assert "guest" not in cli_rows[0][1].lower() and "anonymous" not in cli_rows[0][1].lower()


def test_guest_identity_with_guest_off_hides_the_moor_row(guest_home, monkeypatch):
    _write_config(monkeypatch, guest_home, "moor:\n  guest: false\n")
    from moor_cli import anon_auth
    assert anon_auth.has_guest() and not anon_auth.guest_enabled()

    from moor_cli.model_switch_providers import list_picker_providers
    assert _moor_rows(list_picker_providers("moor", "", None, None, 50, "moor/welcome")) == []
    assert _cli_moor_rows({"moor": {"guest": False}}) == []


def test_desktop_picker_payload_never_locks_the_free_tier_row(guest_home, monkeypatch):
    """``model.options`` (the desktop's path) prices rows from caches on a normal open; the free-tier
    row has no Portal pricing and no entitlement to read, so it must be left alone rather than locked."""
    from moor_cli import inventory
    monkeypatch.setattr(inventory, "_prewarm_pricing_async", lambda *a, **k: None)
    payload = inventory.build_model_options_payload(inventory.load_picker_context())
    rows = _moor_rows(payload["providers"])
    assert len(rows) == 1
    row = rows[0]
    assert row["free_tier_row"] is True
    assert row["models"] == ["moor/welcome"]
    assert row.get("unavailable_models", []) == []
    assert not row.get("free_tier_pending") and not row.get("pricing_pending")
