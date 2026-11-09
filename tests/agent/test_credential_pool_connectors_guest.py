"""A guest that does not carry inference here never serves inference through the credential pool.

A guest that claimed the welcome trial on the desktop's local backend leaves a ``device_code`` row
in ``credential_pool.moor``. In a process that is not that backend (plain CLI, gateway) the pool must
drop that row instead of handing its welcome-host token to the runtime.
"""

from moor_cli import anon_auth
from tests.moor_cli.anon_portal import claimed_trial, install_portal, off_local_desktop


def test_a_claimed_guest_pool_row_serves_every_surface(monkeypatch, tmp_path):
    from agent.credential_pool import load_pool
    from moor_cli.auth_moor import resolve_moor_runtime_credentials

    install_portal(monkeypatch, tmp_path)
    claimed_trial(monkeypatch)
    resolve_moor_runtime_credentials()  # the claimed guest now carries an inference token
    assert any(e.source == "device_code" for e in load_pool("moor").entries())

    off_local_desktop(monkeypatch)  # cron, the CLI, a side agent: not the Desktop

    assert any(e.source == "device_code" for e in load_pool("moor").entries())
