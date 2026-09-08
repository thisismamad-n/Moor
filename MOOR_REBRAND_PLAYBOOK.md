# MOOR REBRAND PLAYBOOK — Instructions for AI Agents

**Read this file completely before touching anything.** It is the canonical
handoff document for any AI agent (or human) maintaining the Moor fork of
upstream `NousResearch/hermes-agent`. It explains what was done, why, how to
continue the work, every known trap, and how to verify you have not broken
anything.

Companion docs: `MOOR_WORKFLOW.md` (user-facing workflow summary).

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
| **IMMUNE** | Files the engine must never touch | `scripts/rebrand.py`, `scripts/rebrand_selftest.py`, `scripts/rebrand_inventory.py`, `agent/legacy_home_migration.py`, `.github/workflows/sync-upstream.yml`, `MOOR_WORKFLOW.md`, this file, `.mailmap`, `contributors/emails/**` |

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

During Phase 5 (`ASSETS`), `scripts/rebrand.py` automatically copies these canonical files into all required destinations:
- `apps/desktop/assets/` (`icon.ico`, `icon.png`, `icon.icns`)
- `apps/bootstrap-installer/src-tauri/icons/` (`icon.ico`, `icon.icns`)
- `apps/desktop/public/` (`apple-touch-icon.png`)
- `website/static/img/` (`apple-touch-icon.png`, `logo.png`, `moor-logo.png`)

### Load-bearing Windows `.exe` icon stamping

The Windows packaging chain reads the icon from two distinct locations:
1. **NSIS Installer (`Moor-<version>-win-x64.exe`)**:
   `electron-builder` packages the installer using `apps/desktop/assets/icon.ico` (specified by `build.icon` in `apps/desktop/package.json`).
2. **Unpacked Application (`Moor.exe`)**:
   Because `build.win.signAndEditExecutable` is disabled to avoid the `winCodeSign` symlink crash, `apps/desktop/scripts/set-exe-identity.mjs` runs via the `afterPack` hook and directly invokes `rcedit` to stamp `apps/desktop/assets/icon.ico` and version metadata onto `Moor.exe`.

### Routine post-rebrand action for desktop

Whenever upstream changes are merged or brand artwork is refreshed:
1. Ensure `brand-assets/` contains the canonical Moor ant icon files (`icon.ico`, `icon.png`, `icon.icns`, `logo.png`).
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

When merging upstream changes or resolving conflicts in the desktop subsystem, preserve Moor's visual and update architecture across the following canonical files:

| Area | Canonical Moor Files | Invariant to Protect |
|---|---|---|
| **Update Architecture** | `apps/desktop/electron/update-remote.ts`<br>`apps/desktop/electron/update-count.ts`<br>`apps/desktop/electron/main.ts`<br>`apps/desktop/electron/preload.ts` | Moor canonical repo (`moor-inc/moor`), PAT injection via `resolveGitAuthArgs` and `resolveUpdateAuthHeaders`, IPC channels `moor:updates:token:*`. |
| **Brand Identity** | `apps/desktop/src/components/brand-mark.tsx`<br>`apps/desktop/assets/` | Moor Ant emblem vector and asset branding (`icon.ico`, `icon.png`, `logo.png`). Never revert to anime or generic squircle icons. |
| **Color System** | `apps/desktop/src/themes/presets.ts`<br>`apps/desktop/src/styles.css` | Cyber-Obsidian & Electric Cobalt theme palette tokens. Never revert to plain VS Code theme colors. |
| **Orientation & Workflow** | `apps/desktop/src/app/shell/global-orientation-header.tsx`<br>`apps/desktop/src/app/contrib/controller.tsx` | Global orientation header with active session, project CWD, connection mode pill, and stable `[1]`-`[5]` tab navigation with live badges. |
| **Quick Start** | `apps/desktop/src/components/chat/intro.tsx` | 1-Click Quick-Start Preset Cards (`/inspect`, `/audit`, `run tests`, `/goal`). |
| **Shortcuts** | `apps/desktop/src/components/keyboard-shortcuts-modal.tsx` | Interactive `?` hotkey cheatsheet modal. |
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
3. **Protect Orientation Header & Shell**:
   - In `apps/desktop/src/app/contrib/controller.tsx`, ensure `<GlobalOrientationHeader />` remains mounted above `<LayoutTreeRoot />`.
   - Ensure `<KeyboardShortcutsModal />` remains mounted in the controller.
4. **Run Desktop & Rebrand Verification Commands**:
   ```powershell
   # 1. Run Electron unit tests
   cd apps/desktop
   npx vitest run electron/update-remote.test.ts
   npx vitest run electron/update-count.test.ts

   # 2. Check TypeScript types (both Electron and Renderer)
   npx tsc -p tsconfig.electron.json --noEmit
   npx tsc -p . --noEmit

   # 3. From repository root, run rebrand verification
   cd ../..
   python scripts/rebrand_selftest.py
   python scripts/rebrand.py --verify
   ```

