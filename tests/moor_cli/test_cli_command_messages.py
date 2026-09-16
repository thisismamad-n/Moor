"""User-facing message contracts for `moor skills/plugins/mcp/cron/doctor` failure paths.

Every failure line must say what happened and name an existing command to type next; none may
lead with a raw exception, a status literal, or a hardcoded ``~/.moor`` path (UX message audit,
findings cli-08/20/21/23/26/34, tools-runtime-13/14/20/27).
"""

from __future__ import annotations

import io
import re
from types import SimpleNamespace

from rich.console import Console


def _console():
    buf = io.StringIO()
    return Console(file=buf, force_terminal=False, width=200, highlight=False, markup=True), buf


# ── skills hub ────────────────────────────────────────────────────────────────────────────────

def test_skill_fetch_failure_names_search_and_doctor():
    from moor_cli.skills_hub import _print_fetch_failure
    c, buf = _console()
    _print_fetch_failure(c, sources=[], identifier="someone/typo-skill")
    out = buf.getvalue()
    assert "moor skills search typo-skill" in out
    assert "moor doctor" in out
    assert "from any source" not in out


def test_scan_block_message_explains_force_and_points_at_inspect():
    from moor_cli.skills_hub import _scan_block_message
    result = SimpleNamespace(verdict="dangerous", trust_level="community", findings=[1, 2, 3])
    msg = _scan_block_message(result, "acme/evil-skill")
    assert "3 high-risk pattern(s)" in msg
    assert "even with --force" in msg
    assert "moor skills inspect acme/evil-skill" in msg
    assert "verdict" not in msg  # scanner jargon stays in the audit log

    soft = _scan_block_message(SimpleNamespace(verdict="suspicious", trust_level="community", findings=[1]),
                               "acme/meh")
    assert "Re-run with --force" in soft


# ── plugins ───────────────────────────────────────────────────────────────────────────────────

def test_plugin_clone_failure_leads_with_next_steps_and_escapes_git_output():
    from moor_cli.plugins_cmd import _clone_failure_message
    msg = _clone_failure_message("https://github.com/acme/nope", "fatal: repository '[x]' not found")
    assert msg.startswith("Could not download the plugin from https://github.com/acme/nope")
    assert "moor plugins search" in msg and "gh auth login" in msg
    assert "Details:" in msg
    assert "\\[x]" in msg  # Rich markup escaped so the raw git text renders verbatim


def test_unknown_plugin_message_points_at_list_and_full_key_rule():
    from moor_cli.plugins_cmd import _unknown_plugin_message
    msg = _unknown_plugin_message("firecrawl")
    assert "No plugin named 'firecrawl'" in msg
    assert "moor plugins list" in msg and "web/firecrawl" in msg and "moor plugins install" in msg
    assert "(none)" not in msg


# ── MCP ───────────────────────────────────────────────────────────────────────────────────────

def test_banner_failed_mcp_line_shows_reason_and_command():
    from moor_cli.banner import _mcp_server_line
    line = _mcp_server_line({"name": "gh", "transport": "stdio", "connected": False, "status": "failed",
                             "error": "missing executable 'npx' (ensure Node.js is installed)"}, dim="grey", text="white")
    assert "could not connect" in line and "missing executable 'npx'" in line
    assert "moor mcp test gh" in line

    auth = _mcp_server_line({"name": "linear", "transport": "http", "connected": False, "status": "failed",
                             "error": "Client error '401 Unauthorized' for url"}, dim="grey", text="white")
    assert "moor mcp login linear" in auth


def test_mcp_probe_failure_unwraps_group_and_points_at_login_for_401():
    from moor_cli.mcp_config import _probe_failure_next_step, _probe_failure_reason

    class _Resp:
        status_code = 401

    class _HttpErr(Exception):
        response = _Resp()

    group = ExceptionGroup("unhandled errors in a TaskGroup", [_HttpErr("Client error '401 Unauthorized'")])
    assert "ExceptionGroup" not in _probe_failure_reason(group)
    assert "401" in _probe_failure_reason(group)
    assert "moor mcp login linear" in _probe_failure_next_step("linear", group)

    missing = FileNotFoundError(2, "No such file or directory", "npx")
    assert "config.yaml" in _probe_failure_next_step("gh", missing)
    assert "~/.moor" not in _probe_failure_next_step("gh", missing) or "profiles" in _probe_failure_next_step("gh", missing)


# ── cron ──────────────────────────────────────────────────────────────────────────────────────

def test_cron_delivery_failure_lines_have_no_status_literals_and_name_the_fix():
    from moor_cli.cron import _cron_doctor_issues_for_job, _job_warnings, _last_run_display
    job = {"id": "job42", "last_status": "delivery_failed", "last_error": None,
           "last_delivery_error": "telegram: 502 Bad Gateway\nsecond raw line", "enabled": False,
           "last_fire_error": {"at": "2026-09-01T07:00:00+00:00",
                               "detail": "scheduled fire could not be forwarded to the gateway api_server"}}
    texts = [_last_run_display(job), *_job_warnings(job), *_cron_doctor_issues_for_job(job)]
    joined = "\n".join(texts)
    assert "delivery_failed" not in joined and "delivery_queued" not in joined
    assert "second raw line" not in joined  # only the first line of the raw blob is shown
    assert "moor cron edit job42 --deliver" in joined
    assert "moor gateway restart" in joined and "moor cron run job42" in joined
    assert "gateway was unreachable" in joined


def test_cron_queued_status_reads_as_in_progress():
    from moor_cli.cron import _last_run_display
    assert "in progress" in _last_run_display({"last_status": "delivery_queued"})


# ── doctor / advisories / paths ───────────────────────────────────────────────────────────────

def test_advisory_remediation_uses_active_moor_home(monkeypatch, tmp_path):
    from moor_cli import security_advisories as sa
    monkeypatch.setattr(sa, "display_moor_home", lambda: "~/.moor/profiles/work")
    hit = SimpleNamespace(advisory=sa.ADVISORIES[0], package="mistralai", installed_version="2.4.6")
    text = "\n".join(sa.full_remediation_text(hit))
    assert "~/.moor/profiles/work/.env" in text
    assert "{moor_home}" not in text
    assert not re.search(r"~/\.moor/\.env", text)


def test_doctor_ack_failure_names_config_path_and_retry(monkeypatch, capsys):
    import moor_cli.doctor as doctor
    monkeypatch.setattr("moor_cli.security_advisories.ack_advisory", lambda _id: False)
    monkeypatch.setattr(doctor, "_DHH", "~/.moor/profiles/work")
    from moor_cli.security_advisories import ADVISORIES
    try:
        doctor._ack_advisory(ADVISORIES[0].id)
    except SystemExit as exc:
        assert exc.code == 1
    out = capsys.readouterr().out
    assert "~/.moor/profiles/work/config.yaml" in out
    assert "moor config path" in out and f"moor doctor --ack {ADVISORIES[0].id}" in out
    assert "Failed to persist" not in out


def test_backup_recovery_hint_cites_the_slash_command_not_a_fake_subcommand():
    from moor_cli.backup import _snapshot_recovery_hint
    hint = _snapshot_recovery_hint()
    assert "/snapshot list" in hint and "/snapshot restore" in hint
    assert "moor snapshot" not in hint  # `moor snapshot` is not a CLI subcommand
    assert "CLI only" in hint  # /snapshot is cli_only; Desktop/gateway readers must not go looking for it
