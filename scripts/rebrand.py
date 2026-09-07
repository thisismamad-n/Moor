#!/usr/bin/env python3
"""Moor rebrand engine — canonical, idempotent, self-healing.

Transforms an upstream ``hermes-agent`` tree (or a partially/damaged
rebranded tree) into the canonical Moor fork state, in one pass:

  1. HEAL      reverse known artifacts of the old root ``rebrand.py``
               (broken URLs like ``github.com/Moor inc./hermes-agent``,
               ``hermes-agent.Moor inc..com``, corrupted model slugs).
  2. FORK      rewrite upstream repo URLs to this fork (optional).
  3. PROTECT   mask spans that must stay byte-identical: live Nous API
               hosts, OAuth endpoints, model slugs, ``NOUS_API_KEY``,
               upstream docker image refs, companion-repo links.
  4. REPLACE   ordered case-aware text ladder (HERMES_/hermes_/Hermes*,
               NOUS_/nous_/Nous*) -> MOOR_/moor_/Moor*, company -> Moor inc.
  5. RENAME    tracked files/dirs whose names contain brand terms
               (hermes_cli -> moor_cli, hey_hermes.onnx -> hey_moor.onnx,
               @hermes/* scopes, tests, docs, docker, nix, ...).
  6. INJECT    re-apply fork-owned hooks upstream merges revert:
               legacy-home migration calls + wake-word audio note.
  7. CLEAN     stale egg-info / __pycache__, legacy root rebrand.py.
  8. VERIFY    zero unexpected brand residuals outside the policy
               allowlist, packaging consistency, compileall, import smoke.

Idempotent: run after every ``git merge upstream/main``. Safe to re-run:
the second run changes nothing (verified in-process).

Recovery: run on a clean git tree; everything is visible via
``git status``; ``git restore . && git clean -fd`` reverts.

Usage:
  python scripts/rebrand.py [--dry-run] [--github-fork OWNER/REPO]
                            [--skip-reinstall] [--no-verify] [--ci]
  python scripts/rebrand.py --verify        # verification only
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COMPANY = "Moor inc."
UPSTREAM_REPO_SLUG = "NousResearch/hermes-agent"
UTF8_BOM = b"\xef\xbb\xbf"

# --------------------------------------------------------------------------
# File selection
# --------------------------------------------------------------------------

IMMUNE_FILES = {
    # The rebrand tooling itself (contains the brand terms by definition).
    "scripts/rebrand.py",
    "scripts/rebrand_selftest.py",
    "scripts/rebrand_inventory.py",
    # Written in final naming; contains legacy-path literals on purpose.
    "agent/legacy_home_migration.py",
    # Documents the hermes->moor mappings themselves; needs the literals.
    "MOOR_WORKFLOW.md",
    # Agent handoff playbook — documents the mappings, needs the literals.
    "MOOR_REBRAND_PLAYBOOK.md",
    # Points at the upstream repo on purpose (it syncs FROM it).
    ".github/workflows/sync-upstream.yml",
    # Git identity data — real humans' emails, never user-facing brand.
    ".mailmap",
}
IMMUNE_PREFIXES = (
    "contributors/emails/",
)

BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".icns", ".pdf",
    ".wav", ".mp3", ".mp4", ".onnx", ".tflite", ".woff", ".woff2",
    ".ttf", ".otf", ".eot", ".zip", ".gz", ".tgz", ".tar", ".bin",
    ".pyc", ".pyd", ".so", ".dll", ".exe", ".dylib", ".db", ".sqlite",
    ".sqlite3", ".wasm", ".node", ".asar", ".bmp", ".tiff",
}

# --------------------------------------------------------------------------
# Heal rules: reverse damage from the old root rebrand.py.
# Old script did \bHermes\b->Moor, \bHERMES\b->MOOR, \bNousResearch\b->Moor inc.
# producing broken shapes. Each rule maps a damaged shape back to the exact
# pristine upstream form; later phases then rebrand it correctly.
# --------------------------------------------------------------------------

HEAL_RULES: list[tuple[str, str]] = [
    (r"Moor inc\./hermes-agent", "NousResearch/hermes-agent"),
    (r"Moor inc\./moor-agent", "NousResearch/hermes-agent"),
    (r"github\.com/Moor inc\./", "github.com/NousResearch/"),
    (r"discord\.gg/Moor inc\.", "discord.gg/NousResearch"),
    (r"((?:[A-Za-z0-9-]+\.)*)Moor inc\.\.(com|wtf|ai|dev|org|net)", r"\1nousresearch.\2"),
    (r"com\.Moor inc\.\.", "com.nousresearch."),
    (r"Moor inc\./((?:[Hh]ermes)[\w.\-]*)", r"NousResearch/\1"),
    (r"Moor-Agent", "moor-agent"),
    (r"nousresearch\.github\.io/moor-agent", "nousresearch.github.io/hermes-agent"),
    # Truncated display hostnames in tests/docs (e.g. "https://hermes-agent
    # .nousresearch..." with literal ellipsis) escaped protection and got
    # half-renamed; restore before re-masking on every run.
    (r"moor-agent\.nousresearch(\.{3})", r"hermes-agent.nousresearch\1"),
]

# --------------------------------------------------------------------------
# Fork URL rewrite: github.com/NousResearch/hermes-agent -> this fork.
# Only the main repo is rewritten; other upstream org resources (models,
# example plugins, docker images) stay pointed at upstream (policy: keep
# external resources functional).
# --------------------------------------------------------------------------

_FORK_REPO_PATH = r"(?:hermes-agent|Hermes-Agent|Hermes-agent|hermes_agent)"
FORK_URL_RULE = re.compile(
    r"github\.com/NousResearch/" + _FORK_REPO_PATH + r"(\.git)?((?:/[^\s\"'`<>)\],;]*)*)"
)


def fork_replacement(fork: str) -> str:
    # fork is OWNER/REPO — the repo name in the slug replaces hermes-agent.
    return f"github.com/{fork}"


# --------------------------------------------------------------------------
# Protected spans — masked during the text ladder, restored verbatim.
# These keep live integrations working: API hosts, OAuth, model slugs.
# --------------------------------------------------------------------------

PROTECT_PATTERNS: list[str] = [
    # Any nousresearch host (portal/api/inference/tool-gateway/firecrawl/
    # audio-gateway/setup/docs/staging/...) with optional URL path, plus
    # truncated display forms ("...nousresearch..." in length tests),
    # GitHub Pages (nousresearch.github.io), and regex literals with escaped dots.
    # Bounded repetition keeps matching linear-time on megabyte lines while
    # still allowing intra-label prefixes (staging-nousresearch.com).
    r"(?:[A-Za-z0-9-]{1,63}\\?\.){0,3}[A-Za-z0-9-]{0,63}nousresearch\\?\.(?:com|wtf|ai|dev|org|net|github\\?\.io|\.\.\.)(?:/[^\s\"'`<>)\]]*)?",
    # Test/example nous hosts.
    r"(?:https?://)?(?:[A-Za-z0-9-]{1,63}\.){0,4}nous\.(?:test|example)(?:/[^\s\"'`<>)\]]*)?",
    # Truncated display hostnames ("https://...nousresearch..." with literal
    # ellipsis in length-test fixtures).
    r"(?:[A-Za-z0-9-]{1,63}\.){0,3}[A-Za-z0-9-]{0,63}nousresearch\.{3}",
    # Upstream Discord invite link stays functional (both casings appear).
    r"(?i:discord\.gg/nousresearch[\w/]{0,100})",
    # Upstream org references that remain after fork rewriting: HF model
    # repos, docker images, companion repos. (github.com/NousResearch/
    # hermes-agent URLs were already rewritten by the fork pass; anything
    # left is an external resource and stays functional.)
    r"[Nn]ous[Rr]esearch/[A-Za-z0-9._/\-]*",
    # Nous-Hermes-N compound model family (before the generic digit rule).
    r"(?i:nous[-_ ]?hermes[-_ ]?\d[\w.\-]*)",
    # Versioned Hermes model slugs: hermes-4-405b, Hermes 3.1, hermes3,
    # hermes_4_70b, FP16_Hermes_4.5 — real model IDs at providers.
    r"(?i:hermes[-_ ]?\d[\w.\-]*)",
    # The Portal credential env var users set at portal.nousresearch.com.
    r"NOUS_API_KEY",
    # Contributor identity: GitHub handle "hermesagent26" (digits required —
    # must NOT swallow HermesAgent class names) and real Reddit permalinks
    # (external history, slugs may embed either brand).
    r"(?i:hermesagent\d{1,4}\b|[\w_]{0,100}hermesagent(?=/)|r/[\w]{0,60}hermesagent\b)",
    r"reddit\.com/r/[A-Za-z0-9_]+/comments/[\w/]*",
    # Third-party community project (hermesatlas.com).
    r"(?i:[\w.-]{0,100}hermesatlas(?:[\w.-]{0,100})?)",
    # Contributor identity mail domain.
    r"[Nn]ous[Rr]esearch\.local",
    # Bare provider-id literals derived from protected hostnames
    # (host-to-provider reverse mapping compares against "nousresearch").
    r"[\"']nousresearch[\"']",
    # Third-party community projects whose names embed the old brand
    # (e.g. the AaronWong1999/hermesclaw WeChat bridge) — external repos,
    # links stay functional.
    r"(?i:[\w.-]{0,100}hermesclaw(?:[\w.-]{0,100})?)",
]

_PROTECT_COMBINED = re.compile("|".join(f"(?:{p})" for p in PROTECT_PATTERNS))

# --------------------------------------------------------------------------
# Text ladder — ordered longest/most-specific first. Case-aware so prose,
# identifiers and env vars each land in the right register.
# --------------------------------------------------------------------------

LADDER: list[tuple[str, str]] = [
    # HERMES family
    (r"HERMES_\*", "MOOR_*"),                       # prose wildcard: `HERMES_*`
    (r"hermes_\*", "moor_*"),
    (r"HERMES_([A-Z0-9_])", r"MOOR_\1"),            # env vars, incl. _HERMES_*
    (r"Hermes_([A-Za-z0-9_])", r"Moor_\1"),
    (r"hermes_([A-Za-z0-9_])", r"moor_\1"),          # hermes_cli, get_hermes_home
    (r"Hermes([A-Z])", r"Moor\1"),                   # HermesAgent, HermesCLI
    (r"hermes-([A-Za-z0-9])", r"moor-\1"),           # hermes-agent, hermes-ink
    (r"Hermes-([A-Za-z0-9][A-Za-z0-9]*)", lambda m: "moor-" + m.group(1).lower()),  # Hermes-Agent -> moor-agent (one pass)
    (r"@hermes/", "@moor/"),                         # npm scope
    (r"com\.nousresearch\.", "com.moorinc."),        # electron/tauri app identifiers
    (r"(?<=_)hermes(?![A-Za-z0-9_])", "moor"),       # snake suffix: hey_hermes, can_update_hermes
    (r"(?<=_)Hermes(?![A-Za-z0-9_])", "Moor"),
    (r"(?<=_)HERMES(?![A-Za-z0-9_])", "MOOR"),
    (r"(?<=_)nous(?![A-Za-z0-9_])", "moor"),
    (r"(?<=_)Nous(?![A-Za-z0-9_])", "Moor"),
    (r"(?<=_)NOUS(?![A-Za-z0-9_])", "MOOR"),
    (r"(?<![A-Za-z0-9-])hermes(?=[A-Z])", "moor"),   # lowerCamel prefix: hermesHome, __hermesMeetQueue
    (r"(?<=[a-z])Hermes(?![A-Za-z0-9_])", "Moor"),   # camel suffix: updateHermes, waitForHermes
    (r"(?<=[a-z])hermes(?![A-Za-z0-9_])", "moor"),
    (r"(?<=[a-z])Nous(?![A-Za-z0-9_])", "Moor"),
    # Compound tokens and special literal forms.
    (r"HERMES_\(", "MOOR_("),                        # /^HERMES_(?:BACKEND|...)_READY/ regex literals
    (r"hermesbot", "moorbot"),                       # IRC/test nick fixtures
    (r"HermesBot", "MoorBot"),
    (r"hermesbench", "moorbench"),                   # internal eval-discipline name
    (r"hermesx", "moorx"),                           # lookalike-module fixture in update-guard tests
    (r"hermesbyt4", "moorbyt4"),                     # docs example bot username
    (r"HERMESPENTEST", "MOORPENTEST"),               # pentest reflection marker
    (r"hermes%3A", "moor%3A"),                       # URL-encoded @hermes: in matrix doc examples
    (r"\bHermest\b", "Moort"),                       # inflected translation (hu: "a Hermest")
    (r"hermesroom", "moorroom"),                     # API server room grant auth scheme
    (r"HermesRoom", "MoorRoom"),
    (r"hermeslocal", "moorlocal"),                   # desktop cert generation pass
    (r"HermesLocal", "MoorLocal"),
    (r"hermesctl", "moorctl"),                       # command fixture in FTS tests
    (r"HermesCtl", "MoorCtl"),
    (r"shermesa", "smoora"),                         # process token boundary test fixture
    # Catch-alls for any remaining prefix forms (prose, quotes, braces,
    # f-strings, regex literals) — everything legitimate above is already
    # handled; whatever is left is brand text.
    (r"HERMES_", "MOOR_"),
    (r"Hermes_", "Moor_"),
    (r"hermes_", "moor_"),
    (r"NOUS_", "MOOR_"),
    (r"Nous_", "Moor_"),
    (r"nous_", "moor_"),
    (r"(?<![A-Za-z0-9_])HERMES(?![A-Za-z0-9_])", "MOOR"),
    (r"(?<![A-Za-z0-9_])Hermes(?![A-Za-z0-9_])", "Moor"),
    (r"(?<![A-Za-z0-9_])hermes(?![A-Za-z0-9_])", "moor"),
    # NOUS family (NousResearch handled before the CamelCase rule)
    (r"NOUS_\*", "MOOR_*"),
    (r"nous_\*", "moor_*"),
    (r"NOUS_([A-Z0-9_])", r"MOOR_\1"),
    (r"Nous_([A-Za-z0-9_])", r"Moor_\1"),
    (r"nous_([A-Za-z0-9_])", r"moor_\1"),
    (r"Nous Research", COMPANY),
    (r"NousResearch", COMPANY),
    (r"Nous([A-Z])", r"Moor\1"),                     # NousProfile -> MoorProfile
    (r"(?<![A-Za-z0-9_])NOUS(?![A-Za-z0-9_])", "MOOR"),
    (r"(?<![A-Za-z0-9_])Nous(?![A-Za-z0-9_])", "Moor"),
    (r"(?<![A-Za-z0-9_])nous(?![A-Za-z0-9_])", "moor"),
]

_LADDER_COMPILED = [(re.compile(p), r) for p, r in LADDER]
# Filenames must not gain spaces: drop the prose company rules for paths.
_PATH_LADDER = [
    (p, r) for p, r in _LADDER_COMPILED
    if callable(r) or " " not in r
]

# --------------------------------------------------------------------------
# Injections — fork-owned hooks that upstream merges revert; re-applied
# idempotently on every run. Anchors are POST-rebrand text.
# --------------------------------------------------------------------------

_MIGRATION_IMPORT = "from agent.legacy_home_migration import ensure_legacy_home_migrated"

INJECTIONS: list[dict] = [
    {
        "file": "moor_cli/main.py",
        "anchor": re.compile(r"^_apply_profile_override\(\)[ \t]*$", re.M),
        "skip_if": "ensure_legacy_home_migrated",
        "insert": f"\n{_MIGRATION_IMPORT}\nensure_legacy_home_migrated()\n",
        "description": "legacy-home migration hook (CLI entry)",
    },
    {
        "file": "gateway/run.py",
        "anchor": re.compile(r'(os\.environ\.setdefault\("MOOR_AGENT", "true"\)\n)'),
        "skip_if": "ensure_legacy_home_migrated",
        "insert": f"    {_MIGRATION_IMPORT}\n    ensure_legacy_home_migrated()\n",
        "description": "legacy-home migration hook (gateway entry)",
    },
    {
        "file": "tools/wake_word.py",
        "anchor": re.compile(r'^_BUNDLED_MODEL_NAME = "hey_moor"$', re.M),
        "skip_if": "LEGACY-AUDIO-MODEL",
        "insert": (
            "\n# LEGACY-AUDIO-MODEL: bundled hotword audio (tools/wakewords/hey_moor.onnx/.tflite) was trained on the\n"
            "# LEGACY-AUDIO-MODEL: ORIGINAL upstream wake phrase — spoken detection still matches that audio\n"
            "# LEGACY-AUDIO-MODEL: until a retrained model is dropped in under the hey_moor name.\n"
        ),
        "description": "wake-word audio-model provenance note",
    },
]

# --------------------------------------------------------------------------
# Untracked junk cleanup (safe-listed patterns only)
# --------------------------------------------------------------------------

CLEANUP_DIR_PATTERNS = [re.compile(p) for p in (r".*\.egg-info", r"__pycache__")]
CLEANUP_SKIP_DIRS = {".git", "node_modules", ".venv", "venv"}
LEGACY_ROOT_SCRIPT = "rebrand.py"

# --------------------------------------------------------------------------
# Optional brand-asset overrides: drop files in brand-assets/ to replace
# binary artwork the transformer cannot regenerate. Name -> destinations.
# --------------------------------------------------------------------------

ASSET_OVERRIDES = {
    "icon.ico": [
        "apps/desktop/assets/icon.ico",
        "apps/bootstrap-installer/src-tauri/icons/icon.ico",
    ],
    "icon.icns": [
        "apps/desktop/assets/icon.icns",
        "apps/bootstrap-installer/src-tauri/icons/icon.icns",
    ],
    "icon.png": [
        "apps/desktop/assets/icon.png",
        "apps/desktop/public/apple-touch-icon.png",
        "website/static/img/apple-touch-icon.png",
    ],
    "favicon.ico": ["web/public/favicon.ico", "website/static/img/favicon.ico"],
    "logo.png": [
        "website/static/img/logo.png",
        "website/static/img/moor-logo.png",
    ],
    "banner.png": ["website/static/img/moor-agent-banner.png"],
    "mascot.jpg": [
        "apps/desktop/public/mascot.jpg",
        "apps/bootstrap-installer/public/mascot.jpg",
    ],
}

# Residual lines allowed by policy (matched against the full line).
ALLOWED_LINE_MARKERS = re.compile(r"LEGACY-[A-Z-]+:")

# Residual scan regexes: hermes anywhere; nous as a word or in compounds.
RESIDUAL_HERMES = re.compile(r"(?i)hermes")
RESIDUAL_NOUS = re.compile(r"(?i)(?<![a-z])nous(?![a-z])|nousresearch")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def git_tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
    ).stdout
    return sorted(p for p in out.decode("utf-8", "replace").split("\0") if p)


def is_immune(rel: str) -> bool:
    return rel in IMMUNE_FILES or rel.startswith(IMMUNE_PREFIXES)


def read_text(raw: bytes) -> tuple[str, str] | None:
    """Decode bytes -> (text, codec). None if binary.

    BOM handling: callers must check ``raw.startswith(UTF8_BOM)`` themselves
    to know whether a BOM was present; decoding with utf-8-sig strips it but
    also succeeds on BOM-less input, so the codec name alone is ambiguous.
    """
    if b"\x00" in raw:
        return None
    body = raw[3:] if raw.startswith(UTF8_BOM) else raw
    try:
        return body.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return body.decode("latin-1"), "latin-1"
    except UnicodeDecodeError:
        return None


def encode_text(text: str, codec: str, had_bom: bool) -> bytes:
    data = text.encode("utf-8" if codec.startswith("utf-8") else codec)
    if had_bom:
        data = UTF8_BOM + data
    return data


def mask_protected(text: str) -> tuple[str, list[str]]:
    store: list[str] = []

    def _sub(m: re.Match) -> str:
        store.append(m.group(0))
        return f"\x00P{len(store) - 1}\x00"

    return _PROTECT_COMBINED.sub(_sub, text), store


def unmask_protected(text: str, store: list[str]) -> str:
    for i in reversed(range(len(store))):
        text = text.replace(f"\x00P{i}\x00", store[i])
    return text


def apply_ladder(text: str, ladder) -> str:
    for pat, repl in ladder:
        text = pat.sub(repl, text)
    return text


def transform_text(text: str, fork: str | None) -> str:
    """Full content pipeline: heal -> fork -> protect -> ladder -> restore."""
    for pat, repl in HEAL_RULES:
        text = re.sub(pat, repl, text)
    if fork:
        text = FORK_URL_RULE.sub(lambda m: fork_replacement(fork) + (m.group(1) or "") + (m.group(2) or ""), text)
    masked, store = mask_protected(text)
    masked = apply_ladder(masked, _LADDER_COMPILED)
    return unmask_protected(masked, store)


def rename_rel_path(rel: str) -> str:
    new = rel
    for pat, repl in _PATH_LADDER:
        new = pat.sub(repl, new)
    return new


def resolve_disk_paths(files: list[str]) -> list[str]:
    """Map index paths to their current on-disk locations.

    Plain moves don't refresh the git index, so after a rename pass
    ``git ls-files`` returns stale paths. For each tracked path prefer the
    path itself; if absent, use its renamed location.
    """
    out = set()
    for rel in files:
        if (REPO / rel).is_file():
            out.add(rel)
            continue
        mapped = rename_rel_path(rel)
        if (REPO / mapped).is_file():
            out.add(mapped)
    return sorted(out)


def detect_fork(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    env = os.environ.get("MOOR_GITHUB_FORK")
    if env:
        return env
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=REPO,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$", url)
    if not m:
        return None
    slug = f"{m.group(1)}/{m.group(2)}"
    if slug.lower().replace("_", "-") in {
        "nousresearch/hermes-agent", "nousresearch/moor-agent",
    }:
        return None
    return slug


# --------------------------------------------------------------------------
# Phases
# --------------------------------------------------------------------------


def phase_contents(files: list[str], fork: str | None, dry: bool) -> tuple[int, int]:
    changed = skipped_binary = 0
    for rel in files:
        if is_immune(rel):
            continue
        path = REPO / rel
        if not path.is_file() or path.is_symlink():
            continue
        raw = path.read_bytes()
        decoded = read_text(raw)
        if decoded is None:
            skipped_binary += 1
            continue
        text, codec = decoded
        had_bom = raw.startswith(UTF8_BOM)
        new_text = transform_text(text, fork)
        if new_text != text:
            changed += 1
            if not dry:
                path.write_bytes(encode_text(new_text, codec, had_bom))
    return changed, skipped_binary


def plan_renames(files: list[str]) -> list[tuple[str, str]]:
    plan: list[tuple[str, str]] = []
    for rel in files:
        if is_immune(rel) or rel.startswith(".git"):
            continue
        new = rename_rel_path(rel)
        if new != rel:
            if " " in Path(new).name:
                print(f"  ! rename would create space in name, skipping: {rel} -> {new}")
                continue
            plan.append((rel, new))
    return plan


def _exists_ci(path: Path) -> bool:
    if path.exists():
        return True
    parent, name = path.parent, path.name
    if not parent.is_dir():
        return False
    return any(child.name.lower() == name.lower() for child in parent.iterdir())


def apply_renames(plan: list[tuple[str, str]], dry: bool) -> int:
    applied = 0
    # Deepest-first so child paths move before their (renamed) ancestors'
    # old directories get pruned; targets are created as needed.
    for old, new in sorted(plan, key=lambda x: -x[0].count("/")):
        src, dst = REPO / old, REPO / new
        if not src.exists():
            if _exists_ci(dst):
                continue  # already moved by a previous run — converged
            print(f"  ! rename source missing and target absent: {old}")
            continue
        if _exists_ci(dst):
            # Stale untracked duplicate at the target (e.g. from an earlier
            # partial rebrand): back it up outside the repo, then move the
            # tracked source through.
            backup_root = Path(tempfile.gettempdir()) / "moor-stale-backup"
            rel_backup = backup_root / new
            rel_backup.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(dst), str(rel_backup))
                print(f"  ~ stale duplicate backed up: {new}")
            except OSError as exc:
                print(f"  ! rename target exists and backup failed ({exc}): {new}")
                continue
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        applied += 1
    if not dry:
        _prune_empty_dirs(REPO)
    return applied


def _prune_empty_dirs(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        d = Path(dirpath)
        if d == root or d.parts[-1] in CLEANUP_SKIP_DIRS or ".git" in d.parts:
            continue
        try:
            next(d.iterdir())
        except StopIteration:
            try:
                d.rmdir()
            except OSError:
                pass
        except OSError:
            pass


def phase_injections(dry: bool) -> list[str]:
    applied, problems = [], []
    for spec in INJECTIONS:
        path = REPO / spec["file"]
        if not path.is_file():
            problems.append(f"injection target missing: {spec['file']}")
            continue
        text = path.read_text(encoding="utf-8")
        if spec["skip_if"] in text:
            continue
        new, n = spec["anchor"].subn(lambda m: m.group(0) + spec["insert"], text, count=1)
        if n == 0:
            problems.append(
                f"injection anchor not found in {spec['file']} ({spec['description']})"
            )
            continue
        if not dry:
            path.write_text(new, encoding="utf-8")
        applied.append(spec["description"])
    return applied, problems


def phase_cleanup(dry: bool) -> list[str]:
    removed = []
    legacy = REPO / LEGACY_ROOT_SCRIPT
    if legacy.is_file() and legacy.resolve() != Path(__file__).resolve():
        if not dry:
            legacy.unlink()
        removed.append(LEGACY_ROOT_SCRIPT)
    for dirpath, dirnames, filenames in os.walk(REPO, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in CLEANUP_SKIP_DIRS]
        for name in dirnames + filenames:
            for pat in CLEANUP_DIR_PATTERNS:
                if pat.fullmatch(name):
                    target = Path(dirpath) / name
                    if not dry:
                        if target.is_dir():
                            shutil.rmtree(target, ignore_errors=True)
                        else:
                            target.unlink(missing_ok=True)
                    removed.append(str(target.relative_to(REPO)))
                    break
    return removed


def phase_assets(dry: bool) -> list[str]:
    src_dir = REPO / "brand-assets"
    if not src_dir.is_dir():
        return []
    copied = []
    for name, dests in ASSET_OVERRIDES.items():
        src = src_dir / name
        if not src.is_file():
            continue
        for dest in dests:
            dp = REPO / dest
            if not dry:
                dp.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dp)
            copied.append(dest)
    return copied


def try_reinstall(dry: bool) -> str:
    if dry:
        return "skipped (dry-run)"
    for candidate in (
        REPO / ".venv" / "Scripts" / "pip.exe",
        REPO / ".venv" / "bin" / "pip",
        REPO / "venv" / "Scripts" / "pip.exe",
        REPO / "venv" / "bin" / "pip",
    ):
        if candidate.is_file():
            try:
                subprocess.run(
                    [str(candidate), "install", "-e", ".", "--no-deps", "--quiet",
                     "--disable-pip-version-check"],
                    cwd=REPO, capture_output=True, timeout=600, check=True,
                )
                return "editable package reinstalled into .venv"
            except (subprocess.SubprocessError, OSError) as exc:
                return f"reinstall failed ({exc}) — run: pip install -e . --no-deps"
    if shutil.which("uv"):
        try:
            subprocess.run(
                ["uv", "pip", "install", "-e", ".", "--no-deps", "--quiet"],
                cwd=REPO, capture_output=True, timeout=600, check=True,
            )
            return "editable package reinstalled into .venv (via uv)"
        except (subprocess.SubprocessError, OSError) as exc:
            return f"reinstall failed ({exc}) — run: uv pip install -e . --no-deps"
    return "no venv pip found — run: pip install -e . --no-deps"


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------


def verify_residuals(files: list[str]) -> tuple[list[dict], int]:
    """Return (unexpected hits, protected/allowed count)."""
    unexpected: list[dict] = []
    allowed = 0
    for rel in files:
        if is_immune(rel):
            continue
        path = REPO / rel
        if not path.is_file() or path.is_symlink():
            continue
        raw = path.read_bytes()
        decoded = read_text(raw)
        if decoded is None:
            continue
        text, _ = decoded
        if not (RESIDUAL_HERMES.search(text) or RESIDUAL_NOUS.search(text)):
            continue
        protected_spans = [m.span() for m in _PROTECT_COMBINED.finditer(text)]
        for m in RESIDUAL_HERMES.finditer(text):
            allowed += _classify(m, text, protected_spans, rel, "hermes", unexpected)
        for m in RESIDUAL_NOUS.finditer(text):
            allowed += _classify(m, text, protected_spans, rel, "nous", unexpected)
    return unexpected, allowed


def _classify(m: re.Match, text: str, spans: list[tuple[int, int]], rel: str, term: str, out: list[dict]) -> int:
    pos = m.start()
    for a, b in spans:
        if a <= pos < b:
            return 1
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    line = text[line_start: line_end if line_end != -1 else len(text)]
    if ALLOWED_LINE_MARKERS.search(line):
        return 1
    out.append({"file": rel, "line": text.count("\n", 0, pos) + 1, "term": term, "line_text": line.strip()[:160]})
    return 0


def verify_boms(resolved_files: list[str]) -> list[str]:
    """BOM parity with HEAD: the transform must never add or drop a BOM.

    Rename-aware: HEAD paths are mapped through the rename plan before
    comparison, so a renamed file is compared against its own origin blob.
    """
    try:
        head_files = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "-z", "HEAD"],
            cwd=REPO, capture_output=True, check=True,
        ).stdout.decode("utf-8", "replace").split("\0")
        grep = subprocess.run(
            ["git", "grep", "-I", "-l", "-P", "\\xef\\xbb\\xbf", "HEAD", "--"],
            cwd=REPO, capture_output=True, text=True,
        )
    except subprocess.SubprocessError:
        return []  # no HEAD (bare/fresh) — nothing to compare
    head_bom_raw = set()
    if grep.returncode == 0:
        head_bom_raw = {ln.removeprefix("HEAD:").replace("\\", "/") for ln in grep.stdout.splitlines()}
    head_bom_mapped = {rename_rel_path(p) for p in head_bom_raw}
    head_mapped = {rename_rel_path(p) for p in head_files if p}
    problems = []
    for rel in resolved_files:
        path = REPO / rel
        if not path.is_file():
            continue
        has_bom = path.read_bytes()[:3] == UTF8_BOM
        head_had = rel in head_bom_mapped
        if has_bom and not head_had and rel in head_mapped:
            problems.append(f"BOM added by transform: {rel}")
        elif not has_bom and head_had:
            problems.append(f"BOM lost by transform: {rel}")
    return problems


def verify_structure() -> list[str]:
    problems = []
    pyproject = REPO / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8-sig"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"pyproject.toml unreadable: {exc}"]
    scripts = data.get("project", {}).get("scripts", {})
    expected = {"moor", "moor-agent", "moor-acp"}
    if set(scripts) != expected:
        problems.append(f"[project.scripts] = {sorted(scripts)}, expected {sorted(expected)}")
    for target in scripts.values():
        mod = target.split(":")[0]
        base = mod.split(".")[0]
        if not ((REPO / f"{base}.py").is_file() or (REPO / base).is_dir()):
            problems.append(f"script target module missing: {mod}")
    for mod in data.get("tool", {}).get("setuptools", {}).get("py-modules", []):
        if not (REPO / f"{mod}.py").is_file():
            problems.append(f"py-modules entry missing on disk: {mod}")
    for pat in data.get("tool", {}).get("setuptools", {}).get("packages", {}).get("include", []):
        base = pat.rstrip(".*").rstrip(".")
        if base and not (REPO / base).is_dir():
            problems.append(f"packages.include dir missing: {base}")
    pkg = REPO / "package.json"
    try:
        import json
        j = json.loads(pkg.read_text(encoding="utf-8-sig"))
        if j.get("name") != "moor-agent":
            problems.append(f"package.json name = {j.get('name')!r}, expected 'moor-agent'")
    except (OSError, ValueError) as exc:
        problems.append(f"package.json unreadable: {exc}")
    return problems


def _resolve_python() -> str:
    for candidate in (
        REPO / ".venv" / "Scripts" / "python.exe",
        REPO / ".venv" / "bin" / "python",
        REPO / "venv" / "Scripts" / "python.exe",
        REPO / "venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def verify_compile() -> list[str]:
    py = _resolve_python()
    out = subprocess.run(
        [py, "-m", "compileall", "-q", "-x",
         r"(^|[/\\])(\.venv|venv|node_modules|\.git|__pycache__)([/\\]|$)",
         str(REPO)],
        cwd=REPO, capture_output=True, text=True, timeout=900,
    )
    lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
    return lines[:40] if out.returncode != 0 else []


def verify_imports() -> tuple[list[str], list[str]]:
    fatal, warnings = [], []
    py = _resolve_python()
    env = dict(os.environ)
    tmp = tempfile.mkdtemp(prefix="moor-home-")
    env["MOOR_HOME"] = str(Path(tmp) / "home")
    env["MOOR_SKIP_HOME_MIGRATION"] = "1"
    required = ["moor_constants", "moor_state", "moor_logging", "moor_time",
                "agent.legacy_home_migration"]
    heavy = ["toolsets", "model_tools", "run_agent", "cli", "moor_cli.main", "gateway.run"]
    for mod in required:
        r = subprocess.run([py, "-c", f"import {mod}"],
                           cwd=REPO, capture_output=True, text=True, env=env, timeout=300)
        if r.returncode != 0:
            fatal.append(f"import {mod}: {r.stderr.strip().splitlines()[-1] if r.stderr else 'unknown'}")
    for mod in heavy:
        r = subprocess.run([py, "-c", f"import {mod}"],
                           cwd=REPO, capture_output=True, text=True, env=env, timeout=300)
        if r.returncode != 0:
            warnings.append(f"import {mod}: {r.stderr.strip().splitlines()[-1] if r.stderr else 'unknown'}")
    shutil.rmtree(tmp, ignore_errors=True)
    return fatal, warnings


def run_verify(files: list[str], ci: bool) -> int:
    print("== VERIFY: residual brand terms ==")
    unexpected, allowed = verify_residuals(files)
    print(f"   allowed (protected/allowlisted): {allowed}")
    if unexpected:
        print(f"   UNEXPECTED RESIDUALS: {len(unexpected)}")
        for hit in unexpected[:80]:
            print(f"     {hit['file']}:{hit['line']} [{hit['term']}] {hit['line_text']}")
    else:
        print("   unexpected residuals: 0")
    problems = verify_structure()
    print("== VERIFY: packaging structure ==")
    print("   OK" if not problems else "\n".join("   ! " + p for p in problems))
    bom_problems = verify_boms(files)
    print("== VERIFY: BOM parity with HEAD ==")
    print("   OK" if not bom_problems else "\n".join("   ! " + p for p in bom_problems[:40]))
    problems = problems + bom_problems
    print("== VERIFY: compileall ==")
    cerr = verify_compile()
    print("   OK" if not cerr else "\n".join("   ! " + ln for ln in cerr))
    print("== VERIFY: import smoke ==")
    fatal, warns = verify_imports()
    for w in warns:
        print(f"   ~ (non-fatal) {w}")
    print("   OK" if not fatal else "\n".join("   ! " + f for f in fatal))
    failed = bool(unexpected or problems or cerr or fatal)
    if failed and ci:
        print("VERIFY FAILED")
        return 2
    if failed:
        print("VERIFY: issues found (see above)")
        return 2
    print("VERIFY: all checks passed")
    return 0


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description="Moor rebrand engine")
    ap.add_argument("--dry-run", action="store_true", help="plan and report, write nothing")
    ap.add_argument("--github-fork", metavar="OWNER/REPO",
                    help="rewrite upstream repo URLs to this fork "
                         "(default: auto-detect from origin remote / MOOR_GITHUB_FORK)")
    ap.add_argument("--skip-reinstall", action="store_true",
                    help="do not reinstall the editable package into .venv")
    ap.add_argument("--no-verify", action="store_true", help="skip verification phase")
    ap.add_argument("--verify", action="store_true", help="verification only")
    ap.add_argument("--ci", action="store_true",
                    help="CI mode: skip reinstall, fail hard on verification errors")
    ap.add_argument("--force", action="store_true",
                    help="run even if the working tree has unrelated uncommitted changes")
    args = ap.parse_args()

    if not (REPO / ".git").exists():
        print("error: must run inside the git repository", file=sys.stderr)
        return 3

    files = resolve_disk_paths(git_tracked_files(REPO))
    fork = detect_fork(args.github_fork)

    if args.verify:
        return run_verify(files, ci=args.ci or True)

    status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout.strip()
    if status and not args.dry_run and not args.force:
        dirty = [ln for ln in status.splitlines()
                 if not ln.endswith("scripts/rebrand_inventory.py")]
        if dirty:
            print("error: working tree has uncommitted changes; commit or stash first")
            for ln in dirty[:10]:
                print(f"  {ln}")
            print("(this keeps the transform reviewable and revertible)")
            return 3

    print(f"Moor rebrand — {len(files)} tracked files, fork={fork or '(upstream URLs kept)'}"
          + (" [DRY RUN]" if args.dry_run else ""))
    print()

    changed, binaries = phase_contents(files, fork, args.dry_run)
    print(f"[1/6] content: {changed} files rewritten, {binaries} binary/text-undecidable skipped")

    plan = plan_renames(files)
    applied = apply_renames(plan, args.dry_run)
    print(f"[2/6] renames: {applied} paths moved")

    inj, problems = phase_injections(args.dry_run)
    print(f"[3/6] injections: {', '.join(inj) if inj else 'none (already present)'}")
    for p in problems:
        print(f"  ! {p}")

    removed = phase_cleanup(args.dry_run)
    print(f"[4/6] cleanup: {len(removed)} items removed (egg-info/__pycache__/legacy script)")

    assets = phase_assets(args.dry_run)
    print(f"[5/6] brand-assets: {len(assets)} overridden" if assets
          else "[5/6] brand-assets: none found (optional: drop files in brand-assets/)")

    if not args.no_verify:
        # Resolve the ORIGINAL tracked list through the rename plan so
        # verification sees post-rename locations even while the git index
        # is still stale (plain moves don't refresh it).
        seen: set[str] = set()
        resolved: list[str] = []
        for rel in files:
            new = rename_rel_path(rel)
            if new not in seen:
                seen.add(new)
                resolved.append(new)
        print("[6/6] verify:")
        rc = run_verify(resolved, ci=args.ci)
        if rc != 0 and args.ci:
            return rc

    reinstall = "skipped (--skip-reinstall)" if args.skip_reinstall else try_reinstall(args.dry_run)
    print()
    print(f"reinstall: {reinstall}")
    print()
    print("Next steps:")
    print("  1. Review with:  git status  /  git diff")
    print("  2. Refresh node workspace links:  npm install --ignore-scripts")
    if not args.skip_reinstall and "reinstalled" not in reinstall:
        print("  3. Reinstall python package:  pip install -e . --no-deps")
    print("  - Re-run any time after 'git merge upstream/main': python scripts/rebrand.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
