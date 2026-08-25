"""Resolve MOOR_HOME for standalone skill scripts.

Skill scripts may run outside the Moor process (system Python, nix env,
CI) where ``moor_constants`` is not importable.  This module provides the
same ``get_moor_home()`` contract without requiring it on ``sys.path``.

When ``moor_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from moor_constants import get_moor_home as get_moor_home
except (ModuleNotFoundError, ImportError):

    def get_moor_home() -> Path:
        """Return the Moor home directory (default: ``~/.moor``)."""
        val = os.environ.get("MOOR_HOME", "").strip()
        return Path(val) if val else Path.home() / ".moor"
