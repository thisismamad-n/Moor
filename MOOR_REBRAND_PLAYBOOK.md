# MOOR REBRAND PLAYBOOK — Instructions for AI Agents

**Read this file completely before touching anything.** It is the canonical
handoff document for any AI agent (or human) maintaining the Moor fork of
upstream `NousResearch/hermes-agent`. It explains what was done, why, how to
continue the work, every known trap, and how to verify you have not broken
anything.

Companion docs: `MOOR_WORKFLOW.md` (user-facing workflow summary), `Moor Specifications and features.md` (custom features, OpenCode emulation, and architecture reference).

---

## 1. Mission & context

This repository is a personal fork of the upstream Hermes agent, fully
rebranded to **Moor** (company: **Moor inc.**). The fork continuously absorbs
upstream updates. Every time upstream content enters the tree, it arrives
full of "hermes"/"nous" terms and must be transformed to the canonical Moor
state — mechanically, completely, and without breaking live functionality.

**This is NOT a one-time migration. It is a permanent, repeatable pipeline.**
The single load-bearing tool is `scripts/rebrand.py`. Everything else in this
document is context for operating and extending it.

### The three-tier policy (memorize this)

| Tier | Rule | Examples |
|---|---|---|
| **REBRAND** | Everything users see or that is internal naming | `hermes_cli`→`moor_cli`, `HERMES_*`→`MOOR_*`, `Hermes`→`Moor`, `Nous Research`→`Moor inc.`, `@hermes/*`→`@moor/*`, file/dir names, `~/.hermes`→`~/.moor`, appId `com.moorinc.*` |
| **PROTECT** | External machine-facing identifiers — renaming silently breaks features | API hosts (`portal.nousresearch.com`, `inference-api.nousresearch.com`, `tool-gateway`, `firecrawl-gateway`, `openai-audio-gateway`, staging hosts, docs host `hermes-agent.nousresearch.com`), model slugs (`hermes-4-405b`, `NousResearch/Hermes-3-Llama-3.1-70B`, `openrouter/nousresearch/hermes-*`), `NOUS_API_KEY`, upstream Docker image refs, upstream Discord invite, contributor identities (`hermesagent26`, `.mailmap`, `contributors/emails/`), third-party project names (`hermesclaw`, `hermesatlas`), Reddit permalinks |
| **IMMUNE** | Files the engine must never touch | `scripts/rebrand.py`, `scripts/rebrand_selftest.py`, `scripts/rebrand_inventory.py`, `agent/legacy_home_migration.py`, `.github/workflows/sync-upstream.yml`, `MOOR_WORKFLOW.md`, `Moor Specifications and features.md`, this file, `.mailmap`, `contributors/emails/**` |

The rationale for PROTECT: these strings are resolved by *other systems*
(OpenRouter, HuggingFace, OAuth servers, Docker Hub, GitHub). Renaming them
produces a "fully branded" app whose login, inference, and model resolution
are silently dead — the worst failure mode. Residual "nous"/"hermes" inside
protected constants is accepted policy; the verifier enforces that nothing
*outside* those constants leaks.

---

## 2. The engine: `scripts/rebrand.py`

### Phase pipeline (order matters)

```
1. HEAL      reverse known damage-shapes from the OLD root rebrand.py
             (e.g. `github.com/Moor inc./hermes-agent` → `github.com/NousResearch/hermes-agent`,
              `Moor inc..com` domains → `nousresearch.com`, `com.Moor inc..hermes` →
              `com.nousresearch.hermes`, `Moor-Agent` → `moor-agent`,
              `moor-agent.nousresearch...` truncated-host fixups)
2. FORK      rewrite github.com/NousResearch/hermes-agent URLs → the fork
             (flag --github-fork, env MOOR_GITHUB_FORK, or auto-detect from
             `git remote get-url origin`; skipped when origin IS upstream)
3. PROTECT   mask protected spans with \x00P<n>\x00 sentinels
4. REPLACE   the ordered text LADDER (see below)
5. RESTORE   unmask protected spans verbatim
6. RENAME    tracked files/dirs via a path-restricted ladder (no spaces)
7. INJECT    re-apply fork-owned hooks upstream merges revert (idempotent,
             anchored on POST-rebrand text):
             - legacy-home migration call in moor_cli/main.py (after
               `_apply_profile_override()`) and gateway/run.py (after
               `os.environ.setdefault("MOOR_AGENT", "true")`)
             - wake-word LEGACY-AUDIO-MODEL note in tools/wake_word.py
               (after `_BUNDLED_MODEL_NAME = "hey_moor"`)
8. CLEAN     delete *.egg-info, __pycache__, legacy root rebrand.py
9. ASSETS    optional brand-assets/ overrides copied onto icon/logo slots
10. VERIFY   hard gates (below)
```

### The ladder (ordered, case-aware — never reorder casually)

Snake/env compounds first, then CamelCase, kebab (with a lambda that
lowercases the tail: `Hermes-Agent`→`moor-agent` in ONE pass), npm scope,
snake-suffix (`hey_hermes`→`hey_moor`), camel-suffix (`updateHermes`→
`updateMoor`), lowerCamel-prefix (`hermesHome`→`moorHome`,
`__hermesMeetQueue`→`__moorMeetQueue`), compound tokens (`hermesbot`,
`hermesbench`, `hermesbyt4`, `HERMESPENTEST`, `hermesx`), prose wildcards
(``HERMES_*``), and finally catch-alls (`HERMES_`→`MOOR_` etc.). The NOUS
family runs with `Nous Research`/`NousResearch`→`Moor inc.` BEFORE the
CamelCase rule (otherwise `NousResearch`→`MoorResearch`).

### Verification gates (all must pass; `--ci` exits non-zero)

1. **Residual scan** — every tracked text file scanned for `hermes` (any
   case) and word-boundary `nous`/`nousresearch`. Each hit is classified:
   inside a protected span → allowed; line carries a `LEGACY-*` marker →
   allowed; else → **UNEXPECTED (must be zero)**.
2. **Packaging structure** — `[project.scripts]` == `{moor, moor-agent,
   moor-acp}`; py-modules exist on disk; packages.find dirs exist;
   `package.json` name == `moor-agent`.
3. **BOM parity with HEAD** — rename-aware comparison of UTF-8 BOM presence
   against the git HEAD blobs. The transform must never add or drop a BOM.
4. **compileall** over the repo.
5. **Import smoke** — required: `moor_constants`, `moor_state`,
   `moor_logging`, `moor_time`, `agent.legacy_home_migration` (fatal on
   failure); heavy: `toolsets`, `model_tools`, `run_agent`, `cli`,
   `moor_cli.main`, `gateway.run` (warn-only).

### CLI flags

```
--dry-run          plan only, write nothing
--github-fork O/R  rewrite upstream repo URLs to this fork
--verify           verification only
--ci               skip reinstall; verification failures exit non-zero
--skip-reinstall   do not pip-install -e . into .venv
--force            run even with unrelated dirty files (use sparingly)
--no-verify        skip phase 10 (for quick iterations)
```

### Expected numbers (anomaly detection)

From **pristine upstream** (9.5k files): ~5,510 files rewritten + ~1,287
renames on run 1; run 2 must be **0 rewrites / 0 renames**. On an already-
converged tree every run is 0/0. If a rerun rewrites anything, you have a
non-idempotent rule — stop and fix it (see §6).

### Performance invariant

Protect patterns use **bounded repetition** (`{0,63}` labels etc.), never
unbounded `[A-Za-z0-9.-]*` prefixes (quadratic blow-up on megabyte lines —
this actually happened and turned a 5-minute run into a 20-minute hang) and
never atomic groups `(?>...)` around prefixes (they prevent the backtracking
needed for `staging-nousresearch.com`-style intra-label matches). Benchmark
before committing regex changes:

```powershell
python -c "import re,time; p='<your pattern>'; s='a.'*20000; t=time.time(); re.search(p,s); print(time.time()-t)"
# must be well under 0.5 s
```

---

## 3. Golden rules

1. **Never hand-edit brand terms in tracked files.** The engine owns them;
   manual edits get reverted by the next run (or worse, create divergence).
   If a term is wrong, fix the RULE, add a selftest case, re-run.
2. **Run on a clean tree.** The script refuses a dirty tree (untracked
   tooling files are tolerated) unless `--force`. Recovery is always
   `git restore . && git clean -fd`.
3. **Idempotency is sacred.** After any rule change: run twice, assert the
   second run reports 0 rewrites / 0 renames.
4. **Every rule change ships with a selftest case.** `scripts/
   rebrand_selftest.py` (66 cases) covers pristine transforms, protected
   spans, heal shapes, fork rewriting, path renames, and an idempotency loop.
   Add cases for every bug you fix.
5. **Never commit or push unless explicitly asked.** The transform is
   designed to be reviewed via `git status`/`git diff` first.
6. **Respect the immune list.** Documentation that documents the mappings
   (`MOOR_WORKFLOW.md`, this file) MUST stay immune — the ladder would eat
   its own "hermes_cli → moor_cli" examples.
7. **Windows file writes must be LF-safe.** The repo enforces LF
   (.gitattributes). NEVER use PowerShell `Set-Content` on source files (it
   converts to CRLF and can add BOMs — this caused a real whole-file phantom
   diff that had to be repaired). Use the editor/Write tool or Python with
   explicit `newline=''` / byte-level writes.
8. **Console output on Windows is cp1252.** The script reconfigures stdout
   to UTF-8 at startup; keep that if you refactor, or emoji in file content
   crash the report.

---

## 4. Routine workflows

### A. After an upstream merge (local)

```powershell
git fetch upstream
git merge upstream/main          # resolve conflicts if any
python scripts/rebrand.py        # heal + protect + rename + verify
git add -A
git commit -m "sync: merge upstream main + reapply Moor rebrand"
git push origin master           # only when the user asks
```

Then refresh toolchains (first time on a machine, or after dependency-affecting
merges): `pip install -e . --no-deps` (or `uv pip install -e . --no-deps`) and
`npm install --ignore-scripts` (refreshes `@moor/*` workspace links).

### B. Automated (GitHub Actions)

`.github/workflows/sync-upstream.yml` runs daily 06:00 UTC + manual dispatch:
checkout → merge upstream → `python scripts/rebrand.py --ci --github-fork
$GITHUB_REPOSITORY` → commit+push. Requirements: repo Settings → Actions →
Workflow permissions → **Read and write**; `origin` must point at the user's
fork (NOT NousResearch — check `git remote -v` if pushes fail). On merge
conflicts the job fails with instructions; conflicts are resolved locally.

Upstream's publish workflows (Docker, site deploy, skills index) carry repo
guards that only fire on `NousResearch/hermes-agent`, so they no-op on the
fork. CI test workflows DO run on the fork — the user may disable them in
the Actions UI.

### C. Adding a new rule (the safe iteration loop)

1. Reproduce: find a real file/line the ladder misses (use
   `scripts/rebrand_inventory.py` or `rg -i 'hermes|nous'`).
2. Decide the tier (§1). If PROTECT: add to `PROTECT_PATTERNS` — check it
   does not swallow legitimate rename targets (see the `hermesagent26` war
   story: an over-broad protect pattern case-insensitively matched
   `HermesAgent` class names and silently froze them).
3. If REBRAND: add to `LADDER` at the correct precedence point (longest/
   most-specific first; catch-alls last).
4. Add a case to `rebrand_selftest.py` (transform + the idempotency loop
   picks it up automatically).
5. `python scripts/rebrand_selftest.py` → all green.
6. `python scripts/rebrand.py --dry-run` → review counts.
7. Real run → **run twice** → second run must be 0/0.
8. `--verify` → all gates green.

### D. Validating the engine against pristine upstream (do this after any
significant engine change)

```powershell
git worktree add D:\Temps\moor-validate <upstream-commit-sha>
# wait for checkout to fully materialize (Windows is slow — Test-Path first)
Copy-Item scripts\rebrand.py D:\Temps\moor-validate\scripts\ -Force
Copy-Item agent\legacy_home_migration.py D:\Temps\moor-validate\agent\ -Force
cd D:\Temps\moor-validate
python scripts\rebrand.py --force --skip-reinstall --no-verify --github-fork acme-test/moor
python scripts\rebrand.py --force --skip-reinstall --no-verify --github-fork acme-test/moor   # must be 0/0
& <main-repo>\.venv\Scripts\python.exe scripts\rebrand.py --verify --ci       # all green
cd <main-repo>
git worktree remove D:\Temps\moor-validate --force
```

Use a REAL upstream commit (`git log upstream/main -1`), not old fork merge
commits — some fork history contains baked-in `<<<<<<< HEAD` conflict
markers that fail compileall for reasons unrelated to the rebrand.

---

## 5. Structural components an agent must know

| Path | Role |
|---|---|
| `scripts/rebrand.py` | The engine (immune). ~800 lines, stdlib only. |
| `scripts/rebrand_selftest.py` | 66-case regression suite (immune). |
| `scripts/rebrand_inventory.py` | Audit tool: brand-term counts by dir/ext/variant (immune). |
| `agent/legacy_home_migration.py` | One-time `~/.hermes`→`~/.moor` copy migration (immune; contains legacy literals on purpose). Copy-only, marker-guarded, skipped when `MOOR_HOME`/`HERMES_HOME` is set (tests/CI/profiles never trigger it). Rewrites `provider: nous`→`moor` and `HERMES_`/`NOUS_` prefixes inside the COPY only. |
| `.github/workflows/sync-upstream.yml` | Daily auto-sync + rebrand + push (immune). |
| `MOOR_WORKFLOW.md` | User-facing summary (immune). |
| `tools/wakewords/hey_moor.onnx/.tflite` | Renamed hotword models — audio still encodes the ORIGINAL phrase (see §7). |

Injection hooks are anchored on post-rebrand text and self-skip via
`skip_if` markers — if upstream renames the anchor lines, the engine reports
`injection anchor not found` as a warning; fix the anchor regex, do not
ignore it.

---

## 6. War stories — bugs already hit and fixed (do not repeat them)

1. **`\bhermes\b` misses compounds.** `_` is a word char: `\bhermes\b` does
   not match `hermes_cli`. Hence the ladder's explicit snake/camel/kebab/
   suffix/prefix rules before any bare-word rule.
2. **camelCase both directions.** `HermesAgent` (prefix) AND `updateHermes`
   (suffix) AND `hermesHome`/`__hermesMeetQueue` (lowerCamel prefix, lookbehind
   must ALLOW underscore) each needed their own rule.
3. **Prose wildcards.** `` `HERMES_*` `` in docs has no identifier char after
   the underscore — needed explicit `HERMES_\*` rules.
4. **Regex-literal env families.** `/^HERMES_(?:BACKEND|DASHBOARD)_READY/`
   has `(` after the underscore — needed `HERMES_\(` before the catch-alls.
5. **Old-script damage shapes.** The legacy root rebrand.py replaced
   `\bNousResearch\b`→`Moor inc.` INSIDE URLs/appIds/emails, producing
   `github.com/Moor inc./hermes-agent`, `Moor inc..com`, `com.Moor inc..hermes`,
   `Moor inc./Hermes-4-405B`. HEAL rules map each damaged shape back to the
   exact pristine form; the normal pipeline then rebrands it correctly. Heal
   runs FIRST, before fork-rewrite and masking.
6. **Two-step non-idempotency.** Ladder produced `Moor-Agent` from pristine
   `Hermes-Agent`, then the `Moor-Agent` heal rule "fixed" it one run later.
   Fix: kebab ladder rule lowercases the tail via lambda in one pass
   (`Hermes-Agent`→`moor-agent`). Lesson: any rule that produces a shape
   another rule consumes = non-idempotent. The run-twice check catches this.
7. **Self-eating injection.** The wake-word note originally contained the
   literal phrase "hey hermes"; run 2's ladder rewrote the note itself.
   Fix: injection text must contain NO brand terms (hence "ORIGINAL upstream
   wake phrase" wording). Same reason immune docs exist.
8. **Catastrophic backtracking.** `[A-Za-z0-9.-]*nousresearch\.` was O(n²)
   on megabyte lines (20-minute hangs). Fix: bounded repetition
   `{1,63}`/`{0,3}`. Do NOT "simplify" back to unbounded classes, and do NOT
   use atomic groups `(?>...)` on those prefixes (breaks intra-label
   matches like `staging-nousresearch.com`).
9. **The BOM bug.** Decoding with `utf-8-sig` first makes `had_bom=True`
   even for BOM-less files → the transform ADDED BOMs to ~5,200 files.
   tomllib/setuptools then failed with `Invalid statement at line 1`.
   Fixed by checking `raw.startswith(UTF8_BOM)` explicitly + the BOM-parity
   verification gate. If you see `Invalid statement (at line 1, column 1)`
   from tomllib anywhere: suspect a BOM first.
10. **Stale git index after renames.** Plain `shutil.move` does not refresh
    the index: `git ls-files` returns OLD paths, so every post-rename run
    silently skipped all moved files (content fixes never reached them).
    Fix: `resolve_disk_paths()` maps index paths → current disk locations.
    If you add phases that enumerate files, they MUST use resolved paths.
11. **Stale untracked duplicates.** An earlier partial rebrand left
    untracked renamed copies at target paths; the rename step skipped
    (target exists) and verification read the stale copy. Fix: backup the
    duplicate to `%TEMP%\moor-stale-backup\` then move the tracked source
    through. If you see surprise residuals in files whose mtime predates
    your session — suspect a stale duplicate.
12. **Verify must resolve paths too.** Verification maps the tracked list
    through the rename plan; otherwise it reads missing old paths and
    reports false green.
13. **`utf-8-sig` in READERS.** `tomllib.loads(text)` fails on a leading
    BOM char; readers in verify use `encoding="utf-8-sig"`. JSON likewise.
14. **Lockfiles are text.** `uv.lock` / `package-lock.json` contain the
    self-referential package name and workspace names; the ladder updates
    them consistently. Do not exclude them. After renames, run
    `npm install --ignore-scripts` to refresh node_modules links.
15. **Editable installs break after renames.** The venv's editable finder
    references old module paths; `pip install -e . --no-deps` (or
    `uv pip install -e . --no-deps`) restores entry points (`moor.exe`,
    `moor-agent.exe`, `moor-acp.exe`). The script does this automatically
    unless `--skip-reinstall`.
16. **Provider config is machine-facing.** `plugins/model-providers/moor/`
    keeps `env_vars=("NOUS_API_KEY",)`, `base_url="https://inference-api.
    nousresearch.com/v1"`, and `fallback_models=("hermes-3-405b", ...)` —
    all PROTECTED. Do not "finish the rebrand" there.
17. **CI repo guards.** Strings like `github.repository == 'NousResearch/
    hermes-agent'` are protected (org-slug pattern). They no-op upstream
    publish jobs on the fork — that is intentional and safe.
18. **Env-var families are prefix-scanned at runtime.**
    `tools/code_execution_tool.py` filters `startswith("MOOR_")`,
    `tools/environments/local.py` uses `_MOOR_FORCE_` prefix, kanban/cron
    isolation tests filter `MOOR_KANBAN_`. The ladder renames producers and
    consumers consistently — never rename one side only.
19. **`is_first_party_module()`** (moor_constants.py) checks
    `root.startswith("moor_")` — the ladder keeps this in sync with the
    renamed modules. Tests mirror it (`test_update_import_guard.py` uses
    lookalike fixtures `hermesx`→`moorx`).
20. **Worktree checkout on Windows materializes lazily.** After
    `git worktree add`, wait and `Test-Path` before copying files in, or
    the copies fail with confusing NotFound errors.
21. **Install endpoints are the deliberate PROTECT exception.** The docs
    host `hermes-agent.nousresearch.com` stays protected — EXCEPT the
    `/install.sh` and `/install.ps1` paths and the bare-domain reinstall
    hints (`reinstall from …`, `reinstall: …`, standalone quoted URL).
    Those are live recovery paths printed when an install is broken; they
    must fetch the fork's own scripts, so `transform_update_source`
    rewrites them to
    `https://raw.githubusercontent.com/thisismamad-n/Moor/master/scripts/…`
    (one-liners, mirroring the desktop bootstrap-runner URL shape) and
    `https://github.com/thisismamad-n/Moor` (bare hints). The rules are
    scoped to those exact wordings/paths — a `…/docs/…` URL never matches.
    Member files: `moor_cli/update_cmd*.py`, `moor_cli/uninstall.py`,
    `moor_constants.py` (plus the original desktop/installer set).
    Covered in `rebrand_selftest.py` `CASES_UPDATE_SOURCE`.

---

## 7. Known functional limitations (do not "fix" mechanically)

- **Wake word audio**: `tools/wakewords/hey_moor.onnx/.tflite` are trained
  embeddings of the ORIGINAL upstream wake phrase. All strings/files are
  renamed, but spoken detection matches the original audio until a retrained
  model is dropped in under the `hey_moor` name. Tracked by the
  `LEGACY-AUDIO-MODEL` comment in `tools/wake_word.py`.
- **Binary artwork**: icons/mascot/banner cannot be regenerated by the
  engine. The user can drop replacements into `brand-assets/` (icon.ico/
  icon.icns/icon.png/favicon.ico/logo.png/banner.png/mascot.jpg); the ASSETS
  phase copies them onto the repo slots.
- **Desktop build output** (`apps/desktop/dist/`, `release/`) is gitignored
  and stale after rebrand; it regenerates on the next desktop build. Old
  `hermes_cli` strings inside built bundles are expected until then.

---

## 8. Desktop executable & binary artwork rebranding checklist (CRITICAL)

Upstream merges frequently pull in the stock upstream logo assets (such as the legacy anime girl icon with the "N" collar). Because binary image files (`.ico`, `.png`, `.icns`) cannot be transformed by text regex ladders, they require explicit asset tracking and compilation reminders.

### Asset storage & auto-sync (`brand-assets/`)

All canonical Moor artwork is permanently stored in `brand-assets/` at the repository root:
- `brand-assets/icon.ico`: Multi-resolution Windows icon (256x256, 128x128, 64x64, 48x48, 32x32, 16x16) featuring the Moor Ant in an Apple-style white squircle.
- `brand-assets/icon.png`: 1024x1024 master icon PNG with transparent outer corners.
- `brand-assets/icon.icns`: Apple macOS bundle icon.
- `brand-assets/logo.png`: 512x512 square logo.
- `brand-assets/filler-bg0.jpg`: Master classical copperplate etching of the Moor Ant among Roman arches and cascading waterfalls in duotone cobalt blue on warm cream vintage paper, serving as the subtle desktop chat backdrop.

During Phase 5 (`ASSETS`), `scripts/rebrand.py` automatically copies these canonical files into all required destinations:
- `apps/desktop/assets/` (`icon.ico`, `icon.png`, `icon.icns`)
- `apps/bootstrap-installer/src-tauri/icons/` (`icon.ico`, `icon.icns`)
- `apps/desktop/public/` (`apple-touch-icon.png`)
- `apps/desktop/public/ds-assets/` (`filler-bg0.jpg`)
- `website/static/img/` (`apple-touch-icon.png`, `logo.png`, `moor-logo.png`)

### Load-bearing Windows `.exe` icon stamping

The Windows packaging chain reads the icon from two distinct locations:
1. **NSIS Installer (`Moor-<version>-win-x64.exe`)**:
   `electron-builder` packages the installer using `apps/desktop/assets/icon.ico` (specified by `build.icon` in `apps/desktop/package.json`).
2. **Unpacked Application (`Moor.exe`)**:
   Because `build.win.signAndEditExecutable` is disabled to avoid the `winCodeSign` symlink crash, `apps/desktop/scripts/set-exe-identity.mjs` runs via the `afterPack` hook and directly invokes `rcedit` to stamp `apps/desktop/assets/icon.ico` and version metadata onto `Moor.exe`.

### Routine post-rebrand action for desktop

Whenever upstream changes are merged or brand artwork is refreshed:
1. Ensure `brand-assets/` contains the canonical Moor ant icon and artwork files (`icon.ico`, `icon.png`, `icon.icns`, `logo.png`, `filler-bg0.jpg`).
2. Run `python scripts/rebrand.py` so the `ASSETS` phase overwrites any upstream image placeholders with Moor's artwork.
3. Recompile the desktop executables:
   ```powershell
   cd apps/desktop
   npm run dist:win:nsis   # packages release/Moor-<version>-win-x64.exe and win-unpacked/Moor.exe
   ```
   Or via the Moor CLI:
   ```powershell
   .venv\Scripts\python.exe -m moor_cli.main desktop --force-build --build-only
   ```
4. Verify the generated executable in `apps/desktop/release/`:
   Check that `Moor-<version>-win-x64.exe` and `win-unpacked/Moor.exe` display the Moor Ant icon and carry Moor metadata (`ProductName: Moor`, `CompanyName: Moor inc.`).

> [!WARNING]
> **Windows Explorer Icon Cache Gotcha**: Windows Explorer aggressively caches `.exe` icon thumbnails in `%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache_*.db` keyed by the file's absolute path. If an `.exe` was previously viewed with an older icon, Explorer may continue rendering the cached thumbnail until the thumbnail cache is cleared, Explorer is restarted, or the file is copied/renamed (e.g. `Moor-Setup.exe`).

---

## 9. Decision framework — proceed vs ask the human

**Proceed autonomously** (engine handles by design): upstream merges, new
files containing brand terms, rule additions with selftest coverage,
verification failures caused by engine gaps (fix the gap), lockfile/package
name updates, binary artwork sync via `brand-assets/`.

**Ask the human** before:
- Changing the three-tier policy (e.g. "scorched-earth" renaming of
  protected endpoints — this breaks Portal login/inference).
- Adding a NEW external endpoint/model-slug to the protect list vs renaming
  it (functional risk).
- Deleting stale untracked duplicates that do NOT match the "generated by
  an earlier script run" profile (possible manual work).
- Any change to `agent/legacy_home_migration.py` semantics (data safety).
- Disabling/altering CI workflows.

---

## 10. Quick reference

```powershell
# State check
python scripts\rebrand_inventory.py          # brand-term census
python scripts\rebrand.py --verify           # all gates (read-only)
python scripts\rebrand.py --dry-run          # what WOULD change

# The loop
python scripts\rebrand_selftest.py           # rule regression suite (must be 66+ green)
python scripts\rebrand.py                    # transform + verify
python scripts\rebrand.py                    # AGAIN — must report 0/0

# Recovery
git restore . ; git clean -fd                # revert everything uncommitted

# Toolchain refresh (after renames)
pip install -e . --no-deps                   # or: uv pip install -e . --no-deps
npm install --ignore-scripts

# Smoke
.venv\Scripts\moor.exe --version             # → "Moor Agent v0.20.2 ..."
```

**Definition of done for any rebrand work**: selftest green → transform run →
second run 0 rewrites/0 renames → `--verify` all gates green (0 unexpected
residuals, packaging OK, BOM parity OK, compileall OK, imports OK) →
`moor --version` works.

---

## 11. Desktop visual brand system & private repository PAT update architecture

Moor Desktop is an independent, executive workstation and must never resemble a generic Hermes or VS Code clone. To ensure downstream merges and the rebrand pipeline do not degrade or revert Moor's visual and update architecture, the following invariants are canonized as part of the official Moor brand.

### A. The Moor Visual Brand System

#### 1. Cyber-Obsidian & Electric Cobalt Palette
The Moor interface communicates computational authority and technical precision. The design system enforces high-contrast brutalist surfaces, architectural hairlines, and vivid cobalt/cyan energy states.

| Token Role | Dark Theme (`moor` / `cyber-obsidian`) | Light Theme (`titanium-paper`) | Purpose & Application |
|---|---|---|---|
| **Background / Canvas** | `#090b10` | `#f8fafc` | Deep cosmic obsidian base; ultra-clean titanium canvas |
| **Surface / Glass Elevation** | `#11141c` | `#ffffff` | Elevated panels, sidebars, context headers, modals |
| **Card Base** | `#161b26` | `#f1f5f9` | Interactive cards, code blocks, preset cards, status items |
| **Border / Hairline** | `#1e2532` | `#e2e8f0` | Subtle structural dividers (0.5px - 1px) |
| **Border Active / Focus** | `#283344` | `#cbd5e1` | Hovered or focused containers |
| **Brand Primary** | `#2563eb` | `#1d4ed8` | Electric cobalt; primary buttons, active indicators |
| **Brand Glow / Accent** | `#3b82f6` | `#2563eb` | Hover highlights, active tab underline, focus rings |
| **Ion Accent (Cyan)** | `#06b6d4` | `#0891b2` | Sensory antennae, AI status nodes, latency indicators |
| **Text Primary** | `#f1f5f9` | `#0f172a` | High-contrast readability for headers and body text |
| **Text Secondary** | `#94a3b8` | `#475569` | Metadata, chips, secondary labels |
| **Text Muted** | `#64748b` | `#94a3b8` | Hotkey badges, inactive tabs, timestamps |
| **Status Warning / Amber** | `#f59e0b` | `#d97706` | PAT authentication alerts, pending audits |
| **Status Success / Emerald** | `#10b981` | `#059669` | Validated credentials, ready state, passing tests |
| **Status Error / Crimson** | `#ef4444` | `#dc2626` | Test failures, network errors, expired tokens |

#### 2. Moor Core Brand Emblem (`MoorAntIcon`)
All legacy anime character artwork and plain rounded squircles are replaced by the official Moor Ant Emblem (`apps/desktop/src/components/brand-mark.tsx`).
- **Vector Geometry**:
  - Head: Angular cybernetic crest with a high-contrast eye slit.
  - Antennae: Forward-reaching dual sensory arcs angled at 38° with glowing ionic terminals (`#06b6d4`).
  - Thorax: Segmented hexagonal armor chassis with high-stress structural joints.
  - Abdomen: Deep tapered hydraulic shell with dual cybernetic energy conduits.
  - Center Node: Glowing cobalt-cyan circular core (`#06b6d4` / `#38bdf8`) with radial energy gradients.
  - Legs: Articulated three-joint stance lines projecting stability and speed.
- **Rendering Modes**:
  - Dark Mode: Obsidian body paths with Electric Cobalt borders, hyper-cyan antennae accents, and cobalt core glow.
  - Light Mode: Deep midnight-slate geometry with crisp cobalt stroke accents.

#### 3. Global Orientation Header ("Never Get Lost")
Mounted at the top of the desktop workstation shell (`apps/desktop/src/app/shell/global-orientation-header.tsx`), providing persistent context regardless of scroll position or sub-pane navigation:
- **Active Session Lineage**: Renders active conversation title, ancestor lineage indicator, and session lock state.
- **Project CWD Chip**: Shows active workspace directory with 1-click clipboard copy (`Ctrl+Click` opens in OS file explorer) and toast feedback.
- **Connection Mode & Latency Pill**: Real-time indicator displaying `Local` (green), `Remote` (cyan), or `Cloud` (purple) with live ping latency (e.g. `24ms`).
- **Active Model Badge**: Crisp pill showing the resolved LLM (e.g., `anthropic/claude-3-7-sonnet`, `deepseek-r1`).
- **Execution State**: Dynamic indicator showing `READY` or pulsing `EXEC` during active agent turns.
- **Stable Tab Navigation `[1]`-`[5]`**: Stable top tabs (`[1] Chat`, `[2] Skills`, `[3] Artifacts`, `[4] Messaging`, `[5] Terminal`) that never shift positions, featuring live status badges (e.g. pending audit count, unread count) and keyboard hotkey indicators `[1]`-`[5]`.

#### 4. 1-Click Quick-Start Preset Cards
Empty chat thread states (`apps/desktop/src/components/chat/intro.tsx`) display instant actionable preset cards:
- **Codebase Deep Inspection** (`/inspect`): Analyzes system architecture, file dependencies, and project invariants.
- **Security & Quality Audit** (`/audit`): Audits security vulnerabilities, lint issues, dead code, and code health.
- **Test Suite Runner** (`run tests`): Triggers project test suites and reports structured failures.
- **Autonomous Goal Runner** (`/goal`): Initiates multi-step, self-verifying autonomous task execution.

#### 5. Keyboard Shortcuts Cheatsheet Modal (`?`)
Global hotkey listener modal (`apps/desktop/src/components/keyboard-shortcuts-modal.tsx`):
- Pressing `?` anywhere in the app (outside active text inputs) opens the cheatsheet modal.
- Tab hotkeys `1` - `5` switch between workstation tabs instantly.
- Execution shortcuts (`Ctrl+Enter` to run, `Ctrl+N` for new session, `Ctrl+Shift+A` to focus agent, `Escape` to close).

#### 6. Strict Zero-Emoji Directive
Emojis are strictly banned across the Moor desktop interface.
- Never use emojis in UI text, status indicators, tabs, buttons, or toast notifications.
- All icons must use clean, scalable Lucide SVG components (e.g., `<Radio />`, `<Terminal />`, `<Layers />`, `<Shield />`, `<Key />`).

#### 7. Swarm Constellation Startup Connecting Overlay (`AntSwarmConnecting`)
Mounted in `apps/desktop/src/components/gateway-connecting-overlay.tsx` via `apps/desktop/src/components/ui/ant-swarm-connecting.tsx`:
- **Canvas Swarm Engine**: 48–64 autonomous worker particles with individual antennae angles, velocities, and decaying pheromone trails converging toward the central Moor hive emblem.
- **Pheromone Signal Lines**: Distance-weighted interconnect lines drawn dynamically between neighboring nodes within proximity threshold.
- **Hexagonal Core Beacon**: Dual rotating concentric radar rings with the central Moor geometric ant mark in a frosted dark glass pod (`#090b10`/90).
- **Live Telemetry Stream**: Real-time rotating matrix telemetry (`SWARM CONSTELLATION LINK`, `BUS: PHEROMONE-IPC`, `NODES: 64 ACTIVE`, `LATENCY: <1ms`).
- **Accessibility Invariant**: Gracefully honors `prefersReducedMotion()`, halts continuous canvas loops, adds `aria-hidden="true"` to canvas, and provides `aria-live="polite"` telemetry announcements.

#### 8. High-Tech Geometric Display Typography (`.wordmark`)
Display lettering in chat empty states and installer flows is anchored in `apps/desktop/src/styles.css`:
- **Font Stack**: Google Fonts `Space Grotesk` (weights 500, 600, 700) and `Syne` (weights 700, 800) with `display=swap` linked in `apps/desktop/index.html`.
- **CSS Rule**:
  ```css
  .wordmark {
    font-family: 'Space Grotesk', 'Syne', 'JetBrains Mono', var(--font-sans), sans-serif;
    font-weight: 700;
    line-height: 0.92;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }
  ```
- **Application**: Bound to `Wordmark` in `apps/desktop/src/components/chat/wordmark.tsx` and welcome titles in `apps/bootstrap-installer/src/routes/welcome.tsx`. Never revert to browser default sans-serif.

#### 9. Unified 3-Zone Single Bar Header & Duplicate Cluster Ban
Mounted in `apps/desktop/src/app/shell/global-orientation-header.tsx`:
- **3-Zone Layout**:
  - **Zone 1 (Left Context)**: Sidebar toggle, Moor ant emblem, active session badge, live status indicator, project CWD button with 1-click clipboard copy.
  - **Zone 2 (Center Navigation Tabs)**: Stable `[1]`-`[5]` workspace tabs with live audit badges and keyboard hotkeys (`[1]` Chat, `[2]` Skills, `[3]` Artifacts, `[4]` Messaging, `[5]` Terminal).
  - **Zone 3 (Right Layout & System Tools)**: Flip panes, right panel toggle, layout grid editor, `?` shortcuts cheatsheet, and settings.
- **OS Chrome Safe Area Invariant**: Header must always include dynamic right padding `calc(var(--titlebar-tools-right, 0px) + 8px)` so buttons never slide under Windows native minimize/maximize/close caption buttons.
- **STRICT BAN on Duplicate Floating Clusters**: Upstream Hermes mounts floating `<TitlebarControls>` at `top: 5px, z-70` in `apps/desktop/src/app/contrib/wiring.tsx`. This causes physical coordinate collision with the header text and tabs. Floating clusters must **NEVER** be re-introduced in `wiring.tsx` — all controls reside strictly within `GlobalOrientationHeader`.

#### 10. Cyber-Industrial Terminal Cockpit Installer UI
Mounted in `apps/desktop/src/components/desktop-install-overlay.tsx` and `apps/bootstrap-installer/src/routes/progress.tsx`:
- **Cockpit Top Status Rail**: Monospace telemetry header (`BOOTSTRAP ENGINE // EXECUTING`, live ping dot, target platform architecture indicator, stage fraction).
- **Segmented Glowing Progress Meter**: Custom 20-segment cyan/emerald progress meter with accessible ARIA semantics (`role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`).
- **Dark Monospace Live Terminal**: Live scrolling stdout/stderr console (`role="log"`, `aria-live="polite"`) with autoscroll, green/cyan log stream, and line count badges.
- **Industrial Choice Cards**: High-contrast dark glass cards for Remote Gateway vs. Local Installation with border glow effects on hover and selection. Never revert to plain white cards.

#### 11. Cyber-Ant Castes Procedural Bot Avatars
Implemented in `apps/desktop/src/plugins/moor-bots/avatar.tsx`, `avatar-image.ts`, and `types.ts`:
- **5 Procedural SVG Castes**:
  1. **Worker (`ant-worker`)**: Geniculate jointed antennae, rounded chitin head, dual glowing compound optic eyes, industrial mandibles.
  2. **Scout (`ant-scout`)**: Swept-back aerodynamic antennae, chevron optic visor, precision mandibles.
  3. **Architect (`ant-architect`)**: Stepped telemetry antennae, hexagonal faceted chitin plates, dual matrix lens eyes, geometric calipers.
  4. **Sentry (`ant-sentry`)**: Heavy armored spikes, tactical horizontal visor slot, reinforced defensive shield plates.
  5. **Commander (`ant-commander`)**: Regal branching antennae, royal crested chitin crown, glowing central power node, commanding compound lenses.
- **Semantic Caste Indicator**: Each vector face includes `data-ant-caste="<caste>"` and `data-bot-face="<name>"`.
- **Default Selection**: `defaultShapeFor(name)` automatically derives an ant caste deterministically from the bot name hash.
- **Generative AI Prompt**: `generateAvatarImage` in `avatar-image.ts` instructs the vision model to generate stylized cybernetic ants with antennae, chitin plates, and optic visors. Never revert to plain circular math faces.

---

### B. Private Repository & Personal Access Token (PAT) Update Architecture

#### 1. Why Upstream Update Checks Fail
Upstream Hermes assumes public GitHub repository access (`NousResearch/hermes-agent`). Because Moor is maintained in a private repository (`github.com/moor-inc/moor` or internal git remote):
- Anonymous `git ls-remote` or `git fetch` operations fail with `401 Unauthorized`, `403 Forbidden`, or attempt to spawn interactive terminal SSH passphrase prompts that freeze desktop background workers.
- Anonymous requests to the GitHub Compare API fail with `404 Not Found` or `401 Bad credentials`.

#### 2. PAT Storage & Configuration Schema
- **Storage File**: `%APPDATA%\Moor\updates.json` (Windows), `~/.config/Moor/updates.json` (Linux), `~/Library/Application Support/Moor/updates.json` (macOS).
- **JSON Schema**:
  ```json
  {
    "branch": "main",
    "pat": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "repo": "moor-inc/moor"
  }
  ```
- **Environment Fallback**: If no token is saved in `updates.json`, the update engine falls back to `GITHUB_TOKEN`, `GH_TOKEN`, or `MOOR_GITHUB_TOKEN` from `process.env`.

#### 3. Non-Interactive Git CLI Authentication
To authenticate git subprocesses without modifying local git credentials or writing tokens to `.git/config`:
- The Electron main process injects git CLI arguments via `-c http.extraHeader="AUTHORIZATION: bearer <token>"`:
  ```typescript
  // apps/desktop/electron/update-remote.ts
  export function resolveGitAuthArgs(pat?: string): string[] {
    if (!pat?.trim()) return [];
    return ['-c', `http.extraHeader=AUTHORIZATION: bearer ${pat.trim()}`];
  }
  ```
- Commands run with `GITHUB_TOKEN` and `GH_TOKEN` populated in `process.env`, and with `GIT_TERMINAL_PROMPT=0` to block GUI credential dialogs:
  ```typescript
  // apps/desktop/electron/main.ts
  const authArgs = resolveGitAuthArgs(tokenConfig.pat);
  await execFileAsync('git', [...authArgs, 'fetch', '--quiet', remoteName, branch], { env: authEnv });
  ```

#### 4. GitHub Compare API Authentication
When comparing commits via the REST API (`api.github.com/repos/{owner}/{repo}/compare/{base}...{head}`):
- Electron injects `Authorization: Bearer <token>` in the HTTP headers:
  ```typescript
  // apps/desktop/electron/update-remote.ts
  export function resolveUpdateAuthHeaders(pat?: string): Record<string, string> {
    const headers: Record<string, string> = {
      'User-Agent': 'Moor-Desktop-Updater/1.0',
      'Accept': 'application/vnd.github.v3+json',
    };
    if (pat?.trim()) {
      headers['Authorization'] = `Bearer ${pat.trim()}`;
    }
    return headers;
  }
  ```

#### 5. In-App Token Configuration & Live Verification
- **Updates Overlay** (`apps/desktop/src/app/updates-overlay.tsx`):
  - When updates fail with `auth-required`, the overlay transitions to `TokenAuthView` prompting for a Personal Access Token with `repo` scope.
  - Provides a 1-click **Verify Access** button that queries `GET https://api.github.com/user` and `GET https://api.github.com/repos/{owner}/{repo}` to confirm token validity and scope before saving.
- **Settings → About** (`apps/desktop/src/app/settings/about-settings.tsx`):
  - Houses the permanent `MoorPatConfigCard` where users can view masked token status, test connection, update their PAT, or configure custom repository URLs.
- **Status Bar Integration** (`apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx`):
  - Displays `Moor: PAT Needed` with an amber warning badge when private repository access requires authentication.

---

### C. Canonized Desktop Files & Merge Preservation Matrix

When merging upstream changes or resolving conflicts in the desktop subsystem, preserve Moor's visual, architectural, and update invariants across the following canonical files:

| Area | Canonical Moor Files | Invariant to Protect |
|---|---|---|
| **Startup Swarm Animation** | `apps/desktop/src/components/ui/ant-swarm-connecting.tsx`<br>`apps/desktop/src/components/gateway-connecting-overlay.tsx`<br>`apps/desktop/src/components/ui/ant-swarm-connecting.test.tsx` | 48-64 node canvas swarm constellation, pheromone trails, rotating antenna rings, and live technical telemetry. Never revert to generic spinning loader. |
| **Wordmark Typography** | `apps/desktop/index.html`<br>`apps/desktop/src/styles.css`<br>`apps/desktop/src/components/chat/wordmark.tsx`<br>`apps/bootstrap-installer/src/routes/welcome.tsx` | Space Grotesk and Syne display font linkage with `&display=swap` and `.wordmark` letter-spacing rule (`0.12em`). Never revert to plain system fonts. |
| **Orientation Header & Wiring** | `apps/desktop/src/app/shell/global-orientation-header.tsx`<br>`apps/desktop/src/app/contrib/wiring.tsx`<br>`apps/desktop/src/lib/icons.ts`<br>`apps/desktop/src/app/shell/titlebar-controls.test.tsx` | Unified 3-zone header with safe area padding `calc(var(--titlebar-tools-right, 0px) + 8px)`. **Strict ban** on floating `<TitlebarControls>` re-introduction in `wiring.tsx`. |
| **Installer Cockpit** | `apps/desktop/src/components/desktop-install-overlay.tsx`<br>`apps/desktop/src/components/desktop-install-overlay.test.tsx`<br>`apps/bootstrap-installer/src/routes/progress.tsx` | Cyber-industrial cockpit layout, top status rail, glowing 20-segment progress meter, and monospace stdout/stderr terminal console. Never revert to plain white card. |
| **Bot Avatars & Ant Castes** | `apps/desktop/src/plugins/moor-bots/avatar.tsx`<br>`apps/desktop/src/plugins/moor-bots/avatar-image.ts`<br>`apps/desktop/src/plugins/moor-bots/types.ts`<br>`apps/desktop/src/plugins/moor-bots/avatar-ant.test.tsx` | 5 procedural SVG Ant Castes (`ant-worker`, `ant-scout`, `ant-architect`, `ant-sentry`, `ant-commander`), `defaultShapeFor` caste defaulting, and AI ant avatar generation prompt. |
| **Brand Identity** | `apps/desktop/src/components/brand-mark.tsx`<br>`apps/desktop/assets/`<br>`brand-assets/` | Moor Ant emblem vector and binary asset branding (`icon.ico`, `icon.png`, `logo.png`). Never revert to anime or generic squircle icons. |
| **Chat Backdrop Artwork** | `apps/desktop/src/components/Backdrop.tsx`<br>`apps/desktop/public/ds-assets/filler-bg0.jpg`<br>`brand-assets/filler-bg0.jpg` | Subtle Moor Ant classical copperplate engraving/woodcut etching in cobalt blue duotone on ivory parchment paper (`opacity-[0.025] mix-blend-difference`). **Strict ban** on reverting to upstream Hermes statue image. Automatically synced from `brand-assets/filler-bg0.jpg` via `rebrand.py`. |
| **Color System** | `apps/desktop/src/themes/presets.ts`<br>`apps/desktop/src/styles.css` | Cyber-Obsidian & Electric Cobalt theme palette tokens. Never revert to plain VS Code theme colors. |
| **Quick Start** | `apps/desktop/src/components/chat/intro.tsx` | 1-Click Quick-Start Preset Cards (`/inspect`, `/audit`, `run tests`, `/goal`). |
| **Shortcuts** | `apps/desktop/src/components/keyboard-shortcuts-modal.tsx` | Interactive `?` hotkey cheatsheet modal. |
| **Update Architecture** | `apps/desktop/electron/update-remote.ts`<br>`apps/desktop/electron/update-count.ts`<br>`apps/desktop/electron/main.ts`<br>`apps/desktop/electron/preload.ts` | Moor canonical repo (`moor-inc/moor`), PAT injection via `resolveGitAuthArgs` and `resolveUpdateAuthHeaders`, IPC channels `moor:updates:token:*`. |
| **Token Management** | `apps/desktop/src/app/updates-overlay.tsx`<br>`apps/desktop/src/app/settings/about-settings.tsx`<br>`apps/desktop/src/store/updates.ts` | PAT token entry, private repo URL override, and live PAT verification. |

---

### D. Upstream Merge Conflict Resolution Guide

Whenever merging changes from upstream Hermes (`NousResearch/hermes-agent`):

1. **Protect Electron Main & Update Logic**:
   - Inspect diffs in `apps/desktop/electron/main.ts`. Upstream changes to `checkUpdates()` must NOT overwrite `resolveGitAuthArgs` or `fetchCompareBehindCount` auth headers.
   - Ensure IPC handlers `moor:updates:token:get`, `moor:updates:token:set`, and `moor:updates:token:verify` remain registered.
2. **Protect Theme & Brand Marks**:
   - In `apps/desktop/src/themes/presets.ts`, keep `moorTheme` / `cyber-obsidian` color values intact.
   - In `apps/desktop/src/components/brand-mark.tsx`, preserve the `MoorAntIcon` SVG markup.
3. **Protect Orientation Header & Ban Wiring Collisions**:
   - In `apps/desktop/src/app/contrib/controller.tsx`, ensure `<GlobalOrientationHeader />` remains mounted above `<LayoutTreeRoot />`.
   - In `apps/desktop/src/app/contrib/wiring.tsx`, ensure upstream's floating `<TitlebarControls>` are NOT re-added, avoiding coordinate collision over the header.
4. **Run Desktop UI & Rebrand Verification Commands**:
   ```powershell
   # 1. Run Desktop UI and Electron unit tests
   cd apps/desktop
   npx vitest run src/components/ui/ant-swarm-connecting.test.tsx src/plugins/moor-bots/avatar-ant.test.tsx src/components/desktop-install-overlay.test.tsx src/components/gateway-connecting-overlay.test.tsx src/app/shell/titlebar-controls.test.tsx
   npx vitest run electron/update-remote.test.ts electron/update-count.test.ts

   # 2. Check TypeScript types (both Electron and Renderer)
   npx tsc -p tsconfig.electron.json --noEmit
   npx tsc -p . --noEmit

   # 3. From repository root, run rebrand verification
   cd ../..
   python scripts/rebrand_selftest.py
   python scripts/rebrand.py --verify
   ```

---

## 12. CLI visual brand system & upstream sync preservation pipeline

Moor CLI is the executive terminal interface for autonomous operations. Downstream upstream merges and the rebrand pipeline must never degrade or revert the Moor CLI back to the legacy Hermes appearance, ASCII art, Greek Caduceus symbols, or gold/amber color palettes.

### A. The Moor CLI Visual Brand System

#### 1. Brutalist "MOOR" Lettermark Banner (`MOOR_AGENT_LOGO`)
Located in `moor_cli/banner.py`:
- 6-line brutalist block ASCII font spanning 43 columns:
  ```
  [bold #38bdf8]███╗   ███╗   ██████╗    ██████╗   ██████╗ [/]
  [bold #3b82f6]████╗ ████║  ██╔═══██╗  ██╔═══██╗  ██╔══██╗[/]
  [#2563eb]██╔████╔██║  ██║   ██║  ██║   ██║  ██████╔╝[/]
  [#2563eb]██║╚██╔╝██║  ██║   ██║  ██║   ██║  ██╔══██╗[/]
  [#06b6d4]██║ ╚═╝ ██║  ╚██████╔╝  ╚██████╔╝  ██║  ██║[/]
  [#0891b2]╚═╝     ╚═╝   ╚═════╝    ╚═════╝   ╚═╝  ╚═╝[/]
  ```
- Rendered when terminal width >= 95 columns.
- Never revert to `HERMES-AGENT` or generic yellow fonts.

#### 2. Precision Cyber-Ant Terminal Hero Emblem (`MOOR_ANT_HERO`)
Located in `moor_cli/banner.py`:
- 13-line, 30-column Braille/Unicode cybernetic ant silhouette:
  - Antennae: Forward sensory arcs angled at 38° with glowing ionic terminals (`#06b6d4`).
  - Head: Angular cybernetic crest with optic visor slit (`#38bdf8`).
  - Thorax & Core: Segmented hexagonal armor chassis with glowing center core node `⬡` (`#2563eb` / `#3b82f6`).
  - Abdomen: Deep tapered hydraulic shell (`#1d4ed8`).
  - Legs: Articulated three-joint stance lines projecting stability and speed (`#1e2532`).
  - Baseline: `[dim #06b6d4]cyber-ant online[/]`
- Replaces the legacy Greek Hermes Caduceus wings/staff.
- Alias `MOOR_CADUCEUS = MOOR_ANT_HERO` is retained for backwards compatibility.

#### 3. Cyber-Obsidian Default Skin & Theme Palette
Defined in `moor_cli/skin_engine.py`:
- Base `default` skin palette:
  - `banner_border`: `#2563eb` (Electric Cobalt)
  - `banner_title`: `#38bdf8` (Bright Cyan)
  - `banner_accent`: `#3b82f6` (Cobalt Glow)
  - `banner_dim`: `#64748b` (Slate Muted)
  - `banner_text`: `#f1f5f9` (High-contrast Titanium)
  - `status_bar_bg`: `#090b10` (Deep Obsidian)
  - `status_bar_text`: `#f1f5f9`
  - `status_bar_strong`: `#38bdf8`
  - `status_bar_dim`: `#64748b`
  - `status_bar_good`: `#10b981` (Emerald)
  - `status_bar_warn`: `#f59e0b` (Amber)
  - `status_bar_bad`: `#ef4444` (Crimson)
  - `status_bar_critical`: `#dc2626`
  - `ui_accent`: `#3b82f6`
  - `ui_label`: `#06b6d4`
  - `input_rule`: `#2563eb`
  - `response_border`: `#2563eb`
  - `completion_menu_bg`: `#090b10`
  - `completion_menu_current_bg`: `#1e293b`
  - `selection_bg`: `#1e2532`
  - `shell_dollar`: `#06b6d4`
  - `voice_status_bg`: `#090b10`
- Contrast floors: Passes all WCAG contrast checks against `#101014` dark pole and `#ffffff` light pole in `tests/moor_cli/test_skin_palettes.py`.
- Legacy gold theme preserved as `"classic-gold"` for users who want retro styling (`moor skin classic-gold`).

#### 4. Persona Branding, Glyphs & Zero-Emoji Directive
- Symbol: Hexagonal Node `"⬡"` (hive/ant cluster). Replaces the Greek Caduceus `"☤"`.
- Help header: `[?] Available Commands`. Replaces kawaii emoji faces `(^_^)?`.
- Farewell: `Session terminated.`. Replaces `Goodbye! ☤`.
- Zero-Emoji Directive: Strict enforcement across all CLI outputs, status bars, and banners.

#### 5. Bundled/Legacy Provider Plugin Compatibility
- Located in `agent/portal_tags.py`:
  - `nous_portal_tags = moor_portal_tags  # LEGACY-PORTAL-TAGS: legacy provider alias`
  - `nous_client_tag = moor_client_tag    # LEGACY-PORTAL-TAGS: legacy client tag alias`
- Prevents `cannot import name 'nous_portal_tags' from 'agent.portal_tags'` crashes when older plugins or cached provider packages attempt to import legacy attribution symbols.

---

### B. Upstream Sync Preservation Pipeline (`phase_cli_branding`)

When merging upstream updates from `NousResearch/hermes-agent`, upstream content arrives with `HERMES-AGENT` block art, Caduceus Braille art, and gold theme defaults. Because regex ladders cannot transform multiline block art or Braille Unicode, `scripts/rebrand.py` incorporates a dedicated Phase:

```
Phase 3b: CLI Branding (phase_cli_branding)
```

1. **Detection & Stamping**:
   - Inspects `moor_cli/banner.py`. If `MOOR_ANT_HERO` is missing or upstream `HERMES-AGENT` / Caduceus art is detected, stamps `_CANONICAL_MOOR_LOGO` and `_CANONICAL_MOOR_ANT_HERO`.
   - Inspects `moor_cli/skin_engine.py`. If `Classic Moor — gold and kawaii` or `Goodbye! ☤` is detected, stamps the Cyber-Obsidian default theme, `classic-gold` skin, and `⬡` branding.
   - Inspects `moor_cli/cli_session_mixin.py` and `moor_cli/cli_tui_mixin.py`. Ensures `Session terminated.` and Cyber-Obsidian fallbacks.
   - Inspects `agent/portal_tags.py`. Ensures `nous_portal_tags = moor_portal_tags` compatibility aliases are intact.
2. **Protected Symbols**:
   - `scripts/rebrand.py` `PROTECT_PATTERNS` explicitly includes `nous_portal_tags = moor_portal_tags` and `nous_client_tag = moor_client_tag` so the text ladder never strips the backward-compatibility aliases.
3. **Idempotency Contract**:
   - Re-running `phase_cli_branding` on an already-converged repository reports `0` changes.

---

### C. CLI Rebrand Verification Commands

After any upstream merge or rebrand rule modification, run:

```powershell
# 1. Verify CLI palette completeness and WCAG contrast floors
.venv\Scripts\pytest.exe tests/moor_cli/test_skin_palettes.py

# 2. Verify CLI visual branding, artwork, and zero-emoji compliance
.venv\Scripts\pytest.exe tests/moor_cli/test_cli_branding.py

# 3. Verify skin engine unit tests
.venv\Scripts\pytest.exe tests/moor_cli/test_skin_engine.py

# 4. Verify portal tags legacy compatibility
.venv\Scripts\pytest.exe tests/agent/test_portal_tags.py

# 5. Run rebrand rule regression suite (108+ cases must pass)
.venv\Scripts\python.exe scripts/rebrand_selftest.py

# 6. Verify vendor independence and dual key resilience
.venv\Scripts\pytest.exe tests/moor_cli/test_rebrand_solutions.py

# 7. Verify full repo residual scan (0 unexpected residuals required)
.venv\Scripts\python.exe scripts/rebrand.py --verify
```

---

## 11. Compiled & Installed Application Surface Isolation (Audio 2 Directive)

### The Core Boundary Rule

When an end user installs `Moor.exe` (Desktop app) or installs the Moor CLI/Python agent runtime, **that machine must never display or leak any reference to `NousResearch` or `Hermes` in any user-facing context**:
- Menus, dialogs, error messages, and onboarding screens
- Logs, diagnostic uploads, and boot failure overlays
- Terminal banners, prompt indicators, and help screens
- External documentation links and support contacts
- Outgoing network attribution headers (`User-Agent`, `HTTP-Referer`, `originator`)
- Multi-language localization bundles

**Crucial Distinction**: Internal fork developer tooling (`scripts/rebrand*.py`, `agent/legacy_home_migration.py`, and this playbook) intentionally contain explanatory mapping tables. That is expected and required. However, **no active compiled or runtime code** may expose legacy brand names to the end user.

---

### Why Naive Renaming Broke the App (The 4 Traps)

Past attempts to blindly rename all occurrences of `hermes` and `nous` broke the application in 4 catastrophic ways:

1. **DNS Resolution & Auth Failures**:
   - Moor inc. does not host an independent OAuth/device-code cluster on `moorinc.com`.
   - Naively rewriting `portal.nousresearch.com` or `inference-api.nousresearch.com` to hypothetical moor domains made DNS lookups fail immediately during `moor auth add moor` or model queries.
   - **Solution**: Keep low-level network API defaults functional in `auth_constants.py` and `providers.py` (with env var overrides `MOOR_PORTAL_URL` and `MOOR_INFERENCE_URL`), while all user-facing UI, documentation, errors, and banners display only "Moor Cloud", "Moor Portal", or Moor GitHub URLs.

2. **Model 404 Not Found Errors**:
   - Upstream inference providers (OpenRouter, HuggingFace, etc.) serve models under canonical slugs (e.g., `hermes-3-llama-3.1-70b`, `hermes-4-405b`).
   - Renaming request slugs broke upstream inference routes.
   - **Solution**: Protect wire-level model IDs in API calls. For user prompts and warnings, use pattern matchers such as `_MOOR_MOOR_NON_AGENTIC_RE` (annotated with `# LEGACY-REBRAND-COMPAT:`) to support both Moor and legacy model names without crashing.

3. **Skills Hub & Catalog Outages**:
   - The Skills Hub and catalogs originally fetched manifests solely from `hermes-agent.nousresearch.com`.
   - Renaming this single host caused the Skills Hub to fail initializing when the endpoint was unreachable or rate-limited.
   - **Solution**: Implement **multi-tier fallback architecture**:
     - **Tier 1 (Primary)**: Fetch from `https://raw.githubusercontent.com/thisismamad-n/Moor/master/...`.
     - **Tier 2 (Fallback)**: Transparent fallback to upstream mirror if tier 1 is unreachable. The application never crashes and the Skills Hub remains 100% available.

4. **Missing Auth Keys in Existing Environments**:
   - Environments that only had `NOUS_API_KEY` configured broke when the code only checked `MOOR_API_KEY`.
   - **Solution**: Implement **dual API key resolution**:
     - Check `MOOR_API_KEY` first.
     - Fall back to `NOUS_API_KEY` transparently.
     - Register `extra_env_vars=("MOOR_API_KEY", "NOUS_API_KEY")` in `MOOR_OVERLAYS["moor"]` and `plugins/model-providers/moor/`.

---

### D. Anti-Regression & Vendor Independence Rules

To ensure that future updates or upstream syncs do not revert these fixes, every developer and agent must strictly follow these rules:

#### Rule 1: Multi-Tier Catalog & Index Fallback Pattern
Any remote catalog, manifest, or skill index fetched by the agent must follow this structure:
```python
# Primary: Moor repository raw GitHub assets
DEFAULT_CATALOG_URL = (
    "https://raw.githubusercontent.com/thisismamad-n/Moor/master/website/static/api/model-catalog.json"
)
# Fallback: Upstream mirrors if primary is unreachable
DEFAULT_CATALOG_FALLBACK_URLS = (
    "https://raw.githubusercontent.com/NousResearch/hermes-agent/main/website/static/api/model-catalog.json",
    "https://hermes-agent.nousresearch.com/docs/api/model-catalog.json",
)
```

#### Rule 2: Outgoing Attribution Headers
All HTTP and WebSocket clients must identify as `MoorAgent`:
- `codex_headers.py`: `User-Agent: MoorAgent/{version}`, `originator: moor-agent`
- `anthropic_adapter.py`: `MoorAgent/{version}`
- `auxiliary_client.py`: `_OR_HEADERS_BASE = {"HTTP-Referer": "https://github.com/thisismamad-n/Moor", "X-Title": "Moor Agent"}`
- `gateway/relay/media.py`: `MoorAgent-Relay/1.0 (+https://github.com/thisismamad-n/Moor)`
- `tools/discord_tool.py`: `moor-agent (https://github.com/thisismamad-n/Moor)`
- All provider plugins in `plugins/model-providers/`: User-Agent set to `MoorAgent` and Referer to Moor GitHub.

#### Rule 3: Dual API Key Resolution
Whenever `MOOR_API_KEY` is referenced, ensure `NOUS_API_KEY` is supported as an alternate/legacy env var in:
- `moor_cli/providers.py` (`MOOR_OVERLAYS["moor"].extra_env_vars`)
- `plugins/model-providers/moor/__init__.py` (`MoorProfile.env_vars`)
- `moor_cli/doctor.py` (`_PROVIDER_ENV_HINTS`)
- `moor_cli/dump.py` (`_ENV_KEYS`)

#### Rule 4: Provider Alias Normalization
`_ALIAS_GROUPS["moor"]` in `moor_cli/providers.py` must always map:
```python
"moor": ("nous", "nousresearch", "moor-portal"),  # LEGACY-REBRAND-COMPAT: fallback provider alias
```
And `agent/agent_init.py` and `agent/auxiliary_client.py` must include `"nous"` in provider sets.

#### Rule 5: Annotation Policy for Policy Verifier
`scripts/rebrand.py --verify` enforces `ALLOWED_LINE_MARKERS = re.compile(r"LEGACY-[A-Z-]+:")`.
- Any line containing legacy terms for backward-compatibility MUST carry:
  `# LEGACY-REBRAND-COMPAT: <reason>`
- Any test line asserting the absence of legacy terms MUST carry:
  `# LEGACY-REBRAND-TEST: <reason>`
Lines without these markers will fail CI and block verification.

#### Rule 6: Desktop Application Hygiene
- Maintainer in `apps/desktop/package.json`: `support@moorinc.com`
- Authors in `apps/bootstrap-installer/src-tauri/Cargo.toml`: `support@moorinc.com`
- All support and diagnostic dialogs in `apps/desktop/src/` must link to `https://github.com/thisismamad-n/Moor/issues` or discussions.
- All remote installation commands in `apps/desktop/src/i18n/*.ts` must use:
  `curl -fsSL https://raw.githubusercontent.com/thisismamad-n/Moor/master/scripts/install.sh | bash`
- Run `npm run typecheck` in `apps/desktop` to ensure TypeScript types pass with 0 errors.

#### Rule 7: Dedicated Regression Test Suite
Always verify changes with:
```powershell
pytest tests/moor_cli/test_rebrand_solutions.py
```
This suite specifically checks:
- Dual API key resolution (`MOOR_API_KEY` + `NOUS_API_KEY`)
- Alias normalization (`nous` / `nousresearch` -> `moor`)
- Outgoing User-Agent attribution
- Canonical repository targets
- Skills Hub and Catalog fallback URLs
- Zero emoji directive compliance on all brand copy

#### Rule 8: Zero Upstream Leak in Bundled Desktop & Gateway Settings
When the desktop application is bundled or installed, all user-facing links, gateway endpoints, and error recovery dialogs must be branded strictly for Moor:
- **Default Moor Portal URL**: `DEFAULT_MOOR_PORTAL_URL` in `apps/desktop/electron/main.ts` and billing fallback in `use-billing-state.ts` must point to Moor domains (`https://portal.moorinc.com`), overridable via `MOOR_PORTAL_BASE_URL`.
- **Gateway Settings Links**: Links in `apps/desktop/src/app/settings/gateway-settings.tsx` (such as `{g.cloudNoAgents.linkText}`) must resolve dynamically through `cloudPortalUrl` (pointing to `${cloudPortalUrl}/agents`), never hardcoding `portal.nousresearch.com`.
- **Installer Syntax & Packaging Integrity**: `scripts/install.ps1` must maintain valid PowerShell AST syntax with 0 parse errors (`[System.Management.Automation.Language.Parser]::ParseFile`) and ensure all fallback tiers (`foreach ($tier in $installTiers)`) are intact so `install.ps1 -Manifest` succeeds during offline/bootstrap initialization.
- **Skills Hub Data Feed**: The Skills Hub endpoint in `skills-hub.tsx` and `catalog-data.ts` remains active so users can browse and install functional community skills without interruption.




