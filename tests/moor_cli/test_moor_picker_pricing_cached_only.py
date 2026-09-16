"""The Moor picker row never starts a pricing fetch: the picker only uses the ids the Portal
unions append, and a cold pricing cache must not hold the picker open (salvage of #102099)."""

import moor_cli.models_pricing as mp
from moor_cli import model_switch_providers as msp


def test_moor_picker_model_ids_reads_pricing_cache_only(monkeypatch):
    seen: list[bool] = []

    def fake_pricing(provider, *, force_refresh=False, cached_only=False):
        seen.append(cached_only)
        return {}

    monkeypatch.setattr(mp, "get_pricing_for_provider", fake_pricing)
    # Keep the sibling Portal calls off the network; only the pricing call shape is under test.
    monkeypatch.setattr("moor_cli.models.check_moor_free_tier", lambda **kw: False)
    monkeypatch.setattr("moor_cli.models.fetch_moor_recommended_models", lambda *a, **kw: None)
    monkeypatch.setattr(mp, "moor_policy_allowed_ids", lambda **kw: None)

    assert msp._moor_picker_model_ids({"moor": ["moor/a"]}, False) == ["moor/a"]
    assert seen == [True]
