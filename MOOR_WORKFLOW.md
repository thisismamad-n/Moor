# Moor Development Workflow

This document explains how **Moor** (a fork of the upstream
`NousResearch/hermes-agent`) stays fully rebranded while continuously
absorbing upstream updates — locally and automatically via GitHub Actions.

---

## 1. The rebrand engine

`scripts/rebrand.py` is the canonical, idempotent, self-healing transformer.
Run it any time the tree contains upstream content (after a merge, or to
repair an old partial rebrand):

```powershell
python scripts/rebrand.py                 # full transform + verify
python scripts/rebrand.py --dry-run       # plan only, write nothing
python scripts/rebrand.py --verify        # verification only
python scripts/rebrand.py --github-fork OWNER/REPO   # rewrite repo URLs to your fork
```

What it does, in order:

1. **Heal** — reverses damage from the old root `rebrand.py` (broken URLs
   like `github.com/Moor inc./hermes-agent`, `hermes-agent.Moor inc..com`,
   corrupted model slugs). Old damage converges to the canonical state.
2. **Fork URLs** — rewrites `github.com/NousResearch/hermes-agent` links to
   your fork (auto-detected from `origin`, `MOOR_GITHUB_FORK`, or the flag).
3. **Protect** — masks spans that must stay byte-identical so live
   integrations keep working:
   - Nous API hosts: `portal.nousresearch.com` (OAuth/billing),
     `inference-api.nousresearch.com`, `api.nousresearch.com`,
     `tool-gateway`, `firecrawl-gateway`, `openai-audio-gateway`, staging
     hosts, and the docs host `hermes-agent.nousresearch.com` (model
     catalog / skills index the agent fetches).
   - Model slugs: `hermes-4-405b`, `Hermes-3-Llama-3.1-70B`,
     `NousResearch/Hermes3`, `openrouter/nousresearch/hermes-*` — real IDs
     at OpenRouter / HuggingFace.
   - `NOUS_API_KEY` (the Portal credential), upstream Docker image refs,
     the upstream Discord invite, contributor identities (`hermesagent26`,
     `.mailmap`, `contributors/emails/`), and third-party project names.
4. **Replace** — ordered case-aware text ladder: `HERMES_*`→`MOOR_*`,
   `hermes_*`→`moor_*`, `Hermes*`→`Moor*`, `nous*`→`moor*`,
   `Nous Research`→`Moor inc.`, npm scope `@hermes/*`→`@moor/*`, app IDs
   →`com.moorinc.*`.
5. **Rename** — tracked files/dirs: `hermes_cli/`→`moor_cli/`,
   `hermes_constants.py`→`moor_constants.py`, `hermes`→`moor` (launcher),
   `hey_hermes.onnx`→`hey_moor.onnx`, `@hermes/ink` package dir, tests,
   docs, docker, nix, systemd, `.desktop`, icons (1,287 paths last pass).
6. **Inject** — re-applies fork-owned hooks upstream merges revert:
   legacy-home migration calls in `moor_cli/main.py` + `gateway/run.py`,
   and the wake-word audio provenance note.
7. **Clean** — stale `egg-info`, `__pycache__`, the legacy root `rebrand.py`.
8. **Verify** — hard gates that fail the run (`--ci`) on:
   - unexpected brand-term residuals (protected/allowlisted terms excluded),
   - packaging structure (entry points `moor`/`moor-agent`/`moor-acp`,
     py-modules, package.json name),
   - **BOM parity with HEAD** (the transform must never add/drop a BOM),
   - `compileall`, and import smoke tests of the core modules.

Idempotency: a second run changes nothing (0 rewrites / 0 renames). This is
checked every run and is what makes the script safe after every merge.

---

## 2. Local update routine

```powershell
git fetch upstream
git merge upstream/main
# resolve conflicts if any, then:
python scripts/rebrand.py
git add -A
git commit -m "sync: merge upstream + reapply Moor rebrand"
git push origin master
```

Recovery: everything the script does is visible in `git status` / `git diff`.
`git restore . && git clean -fd` reverts a run (run it on a clean tree; the
script refuses a dirty tree unless `--force`).

After the first rebrand on a machine, refresh the toolchains:

```powershell
pip install -e . --no-deps        # or: uv pip install -e . --no-deps
npm install --ignore-scripts      # refresh @moor/* workspace links
```

---

## 3. Automatic sync via GitHub Actions

`.github/workflows/sync-upstream.yml` runs daily (06:00 UTC) and on demand:

1. checks out the fork, merges `upstream/main`,
2. runs `scripts/rebrand.py --ci --github-fork $GITHUB_REPOSITORY`,
3. commits `sync: merge upstream main + reapply Moor rebrand` and pushes.

If the merge conflicts, the job fails with instructions — resolve locally
and push. One-time setup: allow GitHub Actions to push
(Settings → Actions → General → Workflow permissions → *Read and write*),
and make sure `origin` points at **your** fork (currently both `origin` and
`upstream` point at `NousResearch/hermes-agent`):

```powershell
git remote set-url origin https://github.com/<you>/moor.git
```

Note: upstream's publish workflows (Docker, site deploy, skills index) carry
repo guards that only fire on `NousResearch/hermes-agent`, so they no-op on
the fork. The test/lint workflows will run on your pushes — disable them in
the Actions UI if you don't want the compute.

---

## 4. Compiled surface isolation & vendor independence

A user who compiles the Desktop application (`Moor.exe`) or installs the CLI runtime must **never see any reference to `NousResearch` or `Hermes`**:
- **User-Facing UI & Errors**: All support links, documentation links, diagnostics dialogs, and error messages point to Moor GitHub (`thisismamad-n/Moor`), Moor issues, and Moor discussions.
- **Multi-Tier Catalogs & Skills Index**: Remote catalogs (`plugin-catalog.json`, `model-catalog.json`, and Skills Hub index) fetch from `thisismamad-n/Moor` raw GitHub as primary, with automatic upstream mirror fallbacks to guarantee 100% uptime.
- **Dual API Key Resolution**: `MOOR_API_KEY` is the primary credential, with `NOUS_API_KEY` supported as an automatic fallback for backward compatibility.
- **Provider Aliases**: The `moor` provider route transparently normalizes legacy `nous`, `nousresearch`, and `moor-portal` slugs.
- **Outgoing Attribution**: Outgoing headers (`User-Agent`, `originator`, `HTTP-Referer`) across all client transports identify strictly as `MoorAgent/{version}` pointing to `https://github.com/thisismamad-n/Moor`.
- **Under the Hood**: Machine-facing network API endpoints (`portal.nousresearch.com`, `inference-api.nousresearch.com`) remain functional as default low-level routes (overridable via `MOOR_PORTAL_URL` and `MOOR_INFERENCE_URL`), so OAuth clusters and model inference don't fail due to missing external servers.
- **Regression Tests**: Any backward-compatibility mapping lines in code MUST carry `# LEGACY-REBRAND-COMPAT:`, and test lines checking the absence of legacy terms MUST carry `# LEGACY-REBRAND-TEST:`. Run `pytest tests/moor_cli/test_rebrand_solutions.py` to verify.

---

## 5. Legacy data migration (`~/.hermes` → `~/.moor`)

`agent/legacy_home_migration.py` copies an existing upstream home
(`~/.hermes` / `%LOCALAPPDATA%\hermes`) into the new Moor home on first
start. Properties: copy-only (upstream stays runnable), once-per-machine
(marker file in the legacy home), skipped whenever `MOOR_HOME`/`HERMES_HOME`
is set (tests, profiles, Docker, CI never trigger it), and it rewrites
`provider: nous` → `provider: moor` plus `HERMES_`/`NOUS_` env prefixes
inside the copied `config.yaml`/`.env` only.

---

## 6. Known functional limitation: wake word

The bundled hotword models (`tools/wakewords/hey_moor.onnx/.tflite`) are
trained audio embeddings of the ORIGINAL upstream wake phrase. Renaming
files and strings is complete, but spoken detection still matches the
original audio until a retrained model is dropped into `tools/wakewords/`
under the `hey_moor` name. The code note in `tools/wake_word.py` (marker
`LEGACY-AUDIO-MODEL`) tracks this.

## 7. Brand assets (optional)

Binary artwork can't be regenerated by the script. Drop replacements into
`brand-assets/` and they are copied over the repo slots on the next run:
`icon.ico` / `icon.icns` / `icon.png` (desktop), `favicon.ico` (dashboard +
website), `logo.png`, `banner.png` (website), `mascot.jpg` (replaces the old
mascot in the desktop app + bootstrap installer).

---

## 8. Tooling reference

| Script / Command | Purpose |
|---|---|
| `scripts/rebrand.py` | Canonical rebrand engine (this whole document) |
| `scripts/rebrand.py --verify` | Strict residual audit (must report 0 unexpected residuals) |
| `scripts/rebrand_selftest.py` | 108-case regression suite for the transform rules |
| `scripts/rebrand_inventory.py` | Audit: counts brand-term occurrences by file/dir/variant |
| `pytest tests/moor_cli/test_rebrand_solutions.py` | Unit tests for vendor independence, dual keys, & fallbacks |
