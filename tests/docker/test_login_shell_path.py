"""Login shells in the image keep Moor' own dirs on PATH.

Debian's ``/etc/profile`` resets PATH for every login shell, so without
``/etc/profile.d/moor.sh`` a ``bash -l`` (``docker exec <c> bash -l``, ssh, the
terminal tool's background ``bash -lic``) lost ``/opt/moor/bin`` and bare
``moor`` exited 127 (#56634).
"""
from __future__ import annotations

import subprocess


def test_login_shell_resolves_moor_to_the_image_shim(built_image: str) -> None:
    r = subprocess.run(
        ["docker", "run", "--rm", "-u", "moor", "--entrypoint", "bash", built_image,
         "-lc", 'echo "moor=$(command -v moor)"; echo "path=$PATH"'],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert r.returncode == 0, r.stderr
    lines = dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)
    assert lines["moor"] == "/opt/moor/bin/moor"
    entries = lines["path"].split(":")
    assert entries.index("/opt/moor/bin") < entries.index("/opt/moor/.venv/bin")
    assert entries.count("/opt/moor/bin") == 1
