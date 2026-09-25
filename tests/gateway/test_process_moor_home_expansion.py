"""Gateway identity-file readers expand a literal ``~`` in MOOR_HOME.

``python -m gateway.run`` never passes through the CLI's ``normalize_moor_home_env()``, so the
process-level home readers (PID/lock/status, lifecycle ledger, heartbeat) must expand on their own
or a fish-style ``MOOR_HOME='~/.moor'`` lands the identity files under ``<cwd>/~/.moor``.
"""

from pathlib import Path

import pytest

from gateway import lifecycle_ledger, shutdown_watchdog, status


@pytest.mark.parametrize(
    "reader",
    [status._get_process_moor_home, lifecycle_ledger._process_moor_home,
     shutdown_watchdog._process_moor_home],
    ids=["status", "lifecycle_ledger", "shutdown_watchdog"],
)
def test_process_home_readers_expand_literal_tilde(reader, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("MOOR_HOME", "~/.x")
    assert reader() == tmp_path / ".x"
    assert reader().is_absolute()
    monkeypatch.setenv("MOOR_HOME", str(tmp_path / ".abs"))
    assert reader() == Path(tmp_path / ".abs")
