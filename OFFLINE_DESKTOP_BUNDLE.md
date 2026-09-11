# Offline Desktop Bundle — first launch with zero network

**Status:** implemented. Every desktop `.exe` built after this change installs
Moor on a fully offline Windows machine. This document explains the failure it
fixes, why the old code fetched from the pre-rebrand remote, exactly what
changed, and what still needs the network (honestly).

Companion: `OFFLINE_INSTALL.md` (CLI-focused setup steps).

---

## 1. The failure (what you saw)

On first launch the desktop app showed:

> **Moor couldn't start** — The background gateway didn't come up.
> `Error invoking remote method 'moor:connection': Error: Moor bootstrap
> failed: Failed to download install.ps1: HTTP 429 from
> https://raw.githubusercontent.com/NousResearch/hermes-agent/<sha>/scripts/install.ps1.`

Two independent defects combine into that one dialog:

1. **The `.exe` carried no installer.** `apps/desktop/package.json`
   `extraResources` shipped only `install-stamp.json` + `icon.ico`. Neither
   `scripts/install.ps1|sh` nor any copy of the Moor source tree was inside
   the package, so first launch *had* to download the installer before doing
   anything else.
2. **The download target was the pre-rebrand remote, and it is
   throttle-prone.** The URL was hardcoded to `raw.githubusercontent.com/NousResearch/hermes-agent/...`.
   GitHub answers large-repo raw/pack requests with repo-scoped HTTP 429s
   under load (see `scripts/install.sh` `clone_repo()` comments, issues
   `#89624`/`#89287` for the same throttle on `git clone`). On an offline
   machine the same code path fails with a socket error instead of a 429 —
   same dialog, same dead end. "Repair install" just retried the same doomed
   download.

---

## 2. Why it named the old remote — the rebrand-gap analysis

The report was right: a Moor-branded app downloading from
`NousResearch/hermes-agent` is an incomplete rebrand. The mechanism is worth
understanding so it is not "fixed" wrongly a second time.

### 2.1 Where the slugs lived

| # | File | Old behaviour |
|---|---|---|
| 1 | `apps/desktop/electron/bootstrap-runner.ts` `downloadInstallScript()` | URL template hardcoded `.../NousResearch/hermes-agent/${ref}/scripts/...` |
| 2 | `apps/bootstrap-installer/src-tauri/src/install_script.rs` `download()` | Same slug hardcoded in the `format!()` URL |
| 3 | `apps/bootstrap-installer/src-tauri/build.rs` | Baked commit/branch pins but **no repo slug** — the binary could not know its own fork |
| 4 | `apps/desktop/scripts/write-build-stamp.mjs` | Stamped commit/branch but **no repo slug** — same gap on the Electron side |
| 5 | `scripts/install.ps1` `$RepoUrlSsh/$RepoUrlHttps`, ZIP fallback URLs | `github.com/NousResearch/hermes-agent` (clone source) |
| 6 | `scripts/install.sh` `REPO_URL_SSH/_HTTPS` | Same |

### 2.2 Why `scripts/rebrand.py` never caught them

The rebrand engine's FORK phase rewrites `github.com/NousResearch/hermes-agent`
URLs to the fork — but only when it *knows* the fork (flag
`--github-fork`, `$MOOR_GITHUB_FORK`, or auto-detect from `origin`). This
checkout's `origin` **is** upstream, so fork rewriting is skipped by design.
On top of that, the residual-scan verifier deliberately tolerates
`NousResearch/hermes-agent` inside URL-shaped spans (they are usually
machine-facing: API hosts, model slugs, CI repo guards — renaming those
silently breaks login/inference/updates, see `MOOR_REBRAND_PLAYBOOK.md`
§1 PROTECT). The bootstrap download URLs hid inside that tolerance: shaped
like protected URLs, but semantically **fork-owned** — they should follow the
Moor repo, not upstream. That is the precise sense in which "the rebrand is
incomplete on that side".

### 2.3 Why the fix is fork-aware resolution, not find-and-replace

Blindly rewriting the slug to `moor-inc/moor` would trade one broken state
for another: until the Moor fork publicly hosts those refs, online installs
from upstream checkouts would 404. So every former hardcode is now a
precedence ladder (details in §4). Moor-fork builds bake their own slug;
upstream checkouts keep working unchanged.

### 2.4 Old-brand strings intentionally LEFT alone

These still name the pre-rebrand project and must not be "finished" by a
mechanical pass:

- `portal.nousresearch.com`, `inference-api.nousresearch.com`,
  `hermes-agent.nousresearch.com` (installer one-liners, remote-install
  hints) — live hosts; renaming breaks downloads and remote setup.
- Model slugs (`hermes-4-405b`, `openrouter/nousresearch/hermes-*`,
  `NOUS_API_KEY`, legacy provider-id literals) — resolved by
  OpenRouter/HuggingFace/OAuth; renaming kills inference and login.
- `github.repository == 'NousResearch/hermes-agent'` CI guards — they no-op
  upstream publish jobs on the fork on purpose.
- `moor_cli/model_catalog.py`, `moor_cli/local_runtime/catalog.py`,
  `moor_cli/plugin_index.py` data feeds — already offline-tolerant (in-repo
  snapshot fallback); re-pointing them requires the fork to *host* the feeds,
  which is a separate infrastructure decision (see §7).

---

## 3. The fix, in one picture

```
BUILD TIME (online, once — the 1-click compiler)
  write-build-stamp.mjs          → build/install-stamp.json   { commit, branch, repo }
  stage-offline-bundle.mjs       → build/repo.zip             (4500+ files, ~42 MB, no .git/node_modules/venvs)
                                 → build/offline-scripts/     (byte-identical install.ps1 + install.sh)
                                 → build/offline-manifest.json(hashes, sizes, stamp)
  electron-builder extraResources→ everything above lands INSIDE the .exe
                                   (resources/repo.zip, resources/scripts/*, ...)

FIRST LAUNCH (offline OK)
  bootstrap-runner resolves install.ps1:
    local checkout → BUNDLED (new: always hits in packaged builds) → cache → download (last resort)
  install.ps1 repository stage:
    $MOOR_BUNDLED_REPO (repo.zip from the .exe) → git clone → GitHub ZIP
  ...uv → git → node → system-packages → repository → python → venv → dependencies → node-deps → path → ...
  stages UP TO AND INCLUDING `repository` need no network for scripts or source.
```

The Tauri `Moor-Setup.exe` path mirrors this: `tauri.conf.json`
`resources` bundles the same three payloads, `build.rs` bakes
`BUILD_PIN_REPO`, and `powershell.rs` already exported `MOOR_BUNDLED_REPO`
to the child — `install.ps1` just never consumed it until now.

---

## 4. Resolution ladders (the contract)

### 4.1 Install-script download repo (`OWNER/REPO`)

Electron: `resolveInstallScriptRepo()` in `bootstrap-runner.ts`.
Tauri: `resolve_install_repo()` in `install_script.rs` (same order).

1. Packaged pin — `install-stamp.json` `repo` (Electron) /
   `BUILD_PIN_REPO` or `StartBootstrapArgs.repo` (Tauri)
2. Runtime override — `$MOOR_GITHUB_REPO`, then `$MOOR_GITHUB_FORK`
3. Upstream default — `NousResearch/hermes-agent` (legacy behaviour)

Build-time stamp resolution (`resolveRepoSlug()` in `write-build-stamp.mjs`,
`resolve_repo_pin()` in `build.rs`): `$MOOR_BUILD_PIN_REPO` (Tauri) /
`$MOOR_GITHUB_REPO` / `$MOOR_GITHUB_FORK` → `$GITHUB_REPOSITORY` (CI) →
`git remote get-url origin` parsed to slug → upstream default.

### 4.2 Install-script source (unchanged order, now satisfiable offline)

`local` (dev checkout) → `bundled` (extraResources — **this is what packaged
builds hit now**) → `cache` (`~/.moor/bootstrap-cache`) → `download`
(GitHub raw at the stamped ref) → `installed-agent`
(`~/.moor/moor-agent/scripts`, dev/self-build fallback) → actionable error.

### 4.3 Repository stage source (new first rung)

`$MOOR_BUNDLED_REPO` zip (env or `-BundledRepo` / `--bundled-repo`) →
SSH clone → HTTPS clone (retried, then blobless) → GitHub ZIP.
A bundled unpack also `git init`s a local snapshot commit and sets `origin`
for future *online* updates, and skips the `-Commit`/`--commit` pin fetch
(the snapshot already IS the stamped tree).

---

## 5. File-by-file changelog

| File | Change |
|---|---|
| `apps/desktop/scripts/stage-offline-bundle.mjs` | **New.** Builds `repo.zip` (via `bundle-repo-archive.mjs`), stages byte-identical `install.ps1|sh`, writes `offline-manifest.json`, verifies all four artifacts. `--verify` mode for CI/the compiler gate. |
| `apps/desktop/scripts/stage-offline-bundle.test.mjs` | **New.** 5 `node:test` cases: staging fidelity, missing/truncated/stale-bundle failures, happy-path verify. |
| `apps/desktop/package.json` | `build` now runs `stage-offline-bundle.mjs`; `extraResources` ships `repo.zip`, both install scripts, `offline-manifest.json`. |
| `apps/desktop/scripts/write-build-stamp.mjs` | Stamp gains `repo` (`resolveRepoSlug()` + `parseRepoSlug()` + `UPSTREAM_REPO`). |
| `apps/desktop/scripts/write-build-stamp.test.mjs` | Updated fallback expectation; new slug-parsing/precedence tests. |
| `apps/desktop/electron/bootstrap-runner.ts` | `resolveInstallScriptRepo()` + `installScriptUrl()` replace the hardcoded pre-rebrand template; network errors now explain the offline rebuild; final rethrow stays `Failed to download…`-prefixed. |
| `apps/desktop/electron/bootstrap-runner.test.ts` | New repo-resolution + URL tests (all 15 green from `apps/desktop`). |
| `apps/bootstrap-installer/.../install_script.rs` | `Pin.repo`, `resolve_install_repo()`, repo-aware `download()` URL, offline hint on HTTP errors, unit test. |
| `apps/bootstrap-installer/.../bootstrap.rs` | `StartBootstrapArgs.repo` → `Pin.repo`; test literals updated. |
| `apps/bootstrap-installer/.../build.rs` | Bakes `BUILD_PIN_REPO` (override → CI → origin → upstream). |
| `apps/bootstrap-installer/.../tauri.conf.json` | `bundle.resources`: both install scripts + `repo.zip`. |
| `scripts/install.ps1` | `-BundledRepo` param (`$MOOR_BUNDLED_REPO` default); `Install-Repository` unpacks the zip first, inits a local snapshot commit, skips network pins for it. |
| `scripts/install.sh` | `--bundled-repo` flag / `$MOOR_BUNDLED_REPO`; `clone_repo()` unpacks with `unzip` first, skips `--commit` fetch for it. |
| `scripts/build-desktop-exe.ps1` | Step 1b: loud `--verify` gate + offline-manifest summary; description documents the offline guarantee. |
| `build-desktop-exe.bat` | Notes the automatic offline bundle (forwards to the `.ps1`). |

---

## 6. Build an offline-capable `.exe` (1-click)

```bat
REM From the repo root — double-click or run:
build-desktop-exe.bat
```

What you should see in the output:

```
[INFO] Offline-first build: repo.zip + install.ps1/sh are staged into
[INFO] the .exe automatically (no network needed on first launch).
...
[OK]   Offline bundle verified: repo.zip (4503 files, 42.08 MB) + 2 install scripts + stamp 6a508c7f [NousResearch/hermes-agent]
...
[OK] Desktop application compiled successfully!
```

If the bundle is missing or stale the build **fails before packaging**
instead of producing an `.exe` that dies on first launch. `npm run build`
inside `apps/desktop` does the same staging; `node
scripts/stage-offline-bundle.mjs --verify` re-checks without rebuilding.
To point a build at the Moor fork's slugs:

```powershell
$env:MOOR_GITHUB_REPO = "moor-inc/moor"   # baked into install-stamp.json → repo
.\build-desktop-exe.bat
```

---

## 7. Honest scope: what still needs the network

The bundle guarantees the app never fails for lack of **the installer or the
Moor source tree**, and every later network failure surfaces as its own
stage's error — never as the cryptic bootstrap 429. On a *virgin* offline
machine these later stages still fetch:

| Stage | Fetches | Offline behaviour today |
|---|---|---|
| `uv` | uv binary | Fails with the stage error; pre-install `uv` or seed `%LOCALAPPDATA%\moor\bin` |
| `git` | PortableGit | Same — pre-install Git |
| `node` | Node.js | **Skipped gracefully** (`skipped=true`, browser tools degrade) |
| `system-packages` | ripgrep, ffmpeg | Stage error, install continues where possible |
| `python` | interpreter via uv | `uv`-cached interpreters are reused |
| `dependencies` | PyPI (`uv sync`, `--offline` retried automatically) | Succeeds iff an `uv` cache is warm; otherwise the stage error names the missing packages |
| `node-deps` | npm registry (`npm ci`) | Needs registry unless `~/.npm` is pre-seeded |
| `platform-sdks` | messaging SDKs | Optional per-SDK failures |

In other words: **scripts + source are 100% offline** (everything up to and
including the `repository` stage); language-ecosystem payloads follow their
own caches. A future step toward fully-sealed virgin installs is vendoring
the `uv` cache + an npm tarball cache into `extraResources` and pointing the
stages at them — deliberately not smuggled into this change (size, licensing
review, and per-platform binaries each deserve their own decision).

Model-catalog / plugin-index feeds already fall back to in-repo snapshots
when unreachable, so the picker and skills work offline.

---

## 8. Verify offline yourself

1. Build the `.exe` per §6 on an **online** machine.
2. Move it to the offline desktop (USB). Install and launch.
3. Expect in `%LOCALAPPDATA%\moor\logs\bootstrap-*.log`:
   `[bootstrap] using bundled install.ps1 at ...\resources\scripts\install.ps1`
   and in the stage log: `Unpacking bundled Moor repository (offline, no download)`.
4. To simulate offline on a dev box: disconnect, wipe
   `%LOCALAPPDATA%\moor\bootstrap-cache`, point `MOOR_HOME` at an empty dir,
   launch. The `repository` stage must still succeed; `uv`/`dependencies` may
   report their own network errors per §7.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Failed to download install.ps1: HTTP 429 from https://raw.githubusercontent.com/NousResearch/hermes-agent/…` | `.exe` built before this change (no bundle) | Rebuild with `build-desktop-exe.bat`; the new error text says so |
| `... HTTP 404 ...` on a self-built `.exe` | Stamp pins an unpushed local commit; no bundle in the build | Same rebuild; bundled script bypasses the fetch entirely |
| Build fails at `stage-offline-bundle --verify` (`MISSING`/`STALE`) | Skipped staging or edited `scripts/install.*` after staging | Re-run `node scripts/stage-offline-bundle.mjs` (or just rebuild) |
| `STALE ... hash differs` | Source installer edited post-stage | Re-stage; the gate prevents shipping a mismatched installer |
| First launch still clones on an offline box | `$MOOR_BUNDLED_REPO` not reaching `install.ps1` (custom driver) | Pass `-BundledRepo <repo.zip>` / `--bundled-repo`, or keep the stock Electron/Tauri drivers which set it |
| `python`/`dependencies` fail offline on a virgin box | Expected per §7 (ecosystem payloads, not bundled) | Pre-seed `uv`/npm caches, or go online once |

---

## 10. Rebrand follow-ups (needs a human decision, not a script)

1. **Canonical Moor repo slug.** `MOOR_GITHUB_REPO` / `--github-fork` is the
   lever; until the fork slug is canonical, builds keep stamping `origin`.
   Flipping the *default* is a one-line change (`UPSTREAM_REPO` /
   `UPSTREAM_INSTALL_REPO` / `resolve_repo_pin()` default) — do it when the
   fork publicly hosts `scripts/install.*`.
2. **User-facing fetch one-liners** (`scripts/install.cmd` comment,
   `website/docs/.../windows-native.md`, `install.ps1`/`install.sh` usage
   banners) still point at upstream so they resolve today. Repoint them in
   the same change as (1).
3. **Data feeds** (`model_catalog.py`, `local_runtime/catalog.py`,
   `plugin_index.py`) need fork-hosted mirrors before repointing; their
   offline fallbacks already hold.
