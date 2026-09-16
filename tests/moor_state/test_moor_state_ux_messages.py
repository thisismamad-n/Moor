"""Plain-language contracts for moor_state user-facing errors (CLI UX message campaign, cluster D)."""

import moor_state
from moor_state import SessionResumeTooLargeError, format_session_db_unavailable


def test_resume_too_large_names_export_and_config_commands():
    text = str(SessionResumeTooLargeError(4312, 4000))
    assert "4312" in text and "4000" in text
    assert "moor sessions export" in text
    assert "moor config set sessions.max_resume_messages 0" in text
    for jargon in ("lineage", "guard", "safe resume limit"):
        assert jargon not in text


def test_resume_too_large_keeps_structured_fields():
    exc = SessionResumeTooLargeError(20_001, 20_000, scope="in its tip segment")
    assert (exc.message_count, exc.limit) == (20_001, 20_000)
    assert isinstance(exc, ValueError)


def test_db_unavailable_points_to_doctor_without_sqlite_internals():
    moor_state._set_last_init_error("OperationalError: database is locked")
    try:
        text = format_session_db_unavailable(details=True)
    finally:
        moor_state._set_last_init_error(None)
    lead, *rest = text.splitlines()
    assert "session history" in lead
    assert "will not be saved" in lead.lower()
    for internal in ("sqlite.org", "WAL", "NFS/SMB/FUSE/ZFS"):
        assert internal not in lead
    assert rest and rest[0].startswith("Details: ") and "database is locked" in rest[0]


def test_db_unavailable_is_one_line_for_chat_surfaces_by_default():
    moor_state._set_last_init_error("OperationalError: database is locked")
    try:
        text = format_session_db_unavailable(prefix="Cannot resume")
    finally:
        moor_state._set_last_init_error(None)
    assert "\n" not in text
    assert "Details:" not in text
    assert text.startswith("Cannot resume:")


def test_db_unavailable_unknown_cause_on_network_drive_points_at_moving_not_doctor_fix():
    moor_state._set_last_init_error("OperationalError: locking protocol")
    try:
        text = format_session_db_unavailable()
    finally:
        moor_state._set_last_init_error(None)
    assert "network" in text
    assert "local disk" in text
    assert "moor doctor --fix" not in text


def test_db_unavailable_without_cause_still_names_doctor():
    moor_state._set_last_init_error(None)
    text = format_session_db_unavailable(details=True)
    assert "moor doctor" in text
    assert "will not be saved" in text.lower()
    assert "Details:" not in text
