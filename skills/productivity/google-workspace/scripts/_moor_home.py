"""Resolve MOOR_HOME for standalone skill scripts.

Skill scripts may run outside the Moor process (e.g. system Python,
nix env, CI) where ``moor_constants`` is not importable.  This module
provides the same ``get_moor_home()`` and ``display_moor_home()``
contracts as ``moor_constants`` without requiring it on ``sys.path``.

When ``moor_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``moor_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``MOOR_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from moor_constants import display_moor_home as display_moor_home
    from moor_constants import get_moor_home as get_moor_home
except (ModuleNotFoundError, ImportError):

    def get_moor_home() -> Path:
        """Return the Moor home directory (default: ~/.moor).

        Mirrors ``moor_constants.get_moor_home()``."""
        val = os.environ.get("MOOR_HOME", "").strip()
        return Path(val) if val else Path.home() / ".moor"

    def display_moor_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``moor_constants.display_moor_home()``."""
        home = get_moor_home()
        try:
            return "~/" + home.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(home)
