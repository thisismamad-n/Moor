"""One-time legacy home migration: ~/.hermes -> ~/.moor.

The Moor fork rebrands the on-disk user-data home. Upstream releases of the
original agent keep using ``~/.hermes`` (POSIX) / ``%LOCALAPPDATA%\\hermes``
(Windows); Moor uses ``~/.moor`` / ``%LOCALAPPDATA%\\moor``. This module
copies an existing legacy home into the new location exactly once so configs,
API keys, sessions, memory, skills and profiles survive the rebrand.

Safety properties (do not weaken):

- Copy, never move. The legacy directory is left untouched so the upstream
  agent remains runnable side-by-side.
- Runs at most once per machine. A ``.legacy-migration-done`` marker is
  written into the LEGACY home on success and checked first.
- Only activates when the resolved current home is the platform DEFAULT and
  ``MOOR_HOME`` is unset. Tests, profiles, Docker, Nix and CI all set
  ``MOOR_HOME``/``HERMES_HOME`` explicitly and therefore never trigger it.
- Never raises into startup: any failure logs a warning and leaves startup
  to proceed with an empty new home.
- Rewrites, inside the COPY only: provider id ``nous`` -> ``moor`` and env
  var prefixes ``HERMES_``/``NOUS_`` -> ``MOOR_`` so credentials and
  overrides keep resolving under the rebranded names.

Entry points call :func:`ensure_legacy_home_migrated` early at startup
(wired by scripts/rebrand.py next to the profile override in
``moor_cli/main.py`` and in ``gateway/run.py::main``).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_MIGRATION_MARKER = ".legacy-migration-done"

_COPY_IGNORE = shutil.ignore_patterns(
    "*.lock", "*.pid", "*.sock", "*.tmp", "*.pyc",
    "__pycache__", "node_modules", ".git",
)

_PROVIDER_LINE = re.compile(r"^(\s*(?:default_)?provider\s*:\s*)(['\"]?)nous\2\s*$", re.M)
_ENV_PREFIX_LINE = re.compile(r"^(\s*(?:export\s+)?)(?:HERMES_|NOUS_)")


def _platform_default_home(flavor: str) -> Path:
    """Platform-default home for flavor="legacy" (upstream) or "current"."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / ("hermes" if flavor == "legacy" else "moor")
    return Path.home() / (".hermes" if flavor == "legacy" else ".moor")


def _env_home_override() -> str | None:
    """Any explicit home env var means "respect the operator's choice".

    ``HERMES_HOME`` is checked too: it is the upstream var name, and someone
    pointing it at a custom location should not have that location silently
    duplicated into the default Moor home.
    """
    return os.environ.get("MOOR_HOME") or os.environ.get("HERMES_HOME")


def ensure_legacy_home_migrated() -> None:
    """Migrate the legacy upstream home into the Moor home, once.

    Cheap no-op in every case except the one that matters: platform-default
    homes, legacy data present, not yet migrated.
    """
    try:
        if _env_home_override():
            return  # explicit home (profile/docker/test/CI) — respect it
        current = _platform_default_home("current")
        legacy = _platform_default_home("legacy")
        if not legacy.is_dir() or current.exists():
            return
        if (legacy / _MIGRATION_MARKER).exists():
            return
        _copy_tree(legacy, current)
        _rewrite_copied_config(current)
        try:
            (legacy / _MIGRATION_MARKER).write_text(
                f"migrated to {current}\n", encoding="utf-8"
            )
            logger.info("Legacy home migrated to %s", display_home(current))
        except OSError as exc:  # marker write failed — don't loop-copy forever
            logger.warning("Could not write migration marker: %s", exc)
    except Exception as exc:  # never break startup
        logger.warning("Legacy home migration skipped: %s", exc)


def display_home(path: Path) -> str:
    """Human-friendly home path for logs (LEGACY-COMPAT display helper)."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _copy_tree(legacy: Path, current: Path) -> None:
    shutil.copytree(legacy, current, ignore=_COPY_IGNORE, symlinks=True)


def _rewrite_copied_config(current: Path) -> None:
    """Rebrand identifiers inside the copied config/.env only."""
    cfg = current / "config.yaml"
    if cfg.is_file():
        try:
            text = cfg.read_text(encoding="utf-8")
            new = _PROVIDER_LINE.sub(lambda m: f"{m.group(1)}{m.group(2)}moor{m.group(2)}", text)
            if new != text:
                cfg.write_text(new, encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Could not rewrite provider id in %s: %s", display_home(cfg), exc)
    envf = current / ".env"
    if envf.is_file():
        try:
            lines = envf.read_text(encoding="utf-8").splitlines(keepends=True)
            out = [_ENV_PREFIX_LINE.sub(r"\1MOOR_", ln) for ln in lines]
            if out != lines:
                envf.write_text("".join(out), encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Could not rewrite env prefixes in %s: %s", display_home(envf), exc)
