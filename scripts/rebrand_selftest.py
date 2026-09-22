"""Unit checks for scripts/rebrand.py transform rules."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebrand as rb  # noqa: E402

CASES_PRISTINE = [
    ("from moor_cli.config import get_moor_home",
     "from moor_cli.config import get_moor_home"),
    ('os.environ["MOOR_HOME"] = x  # MOOR_TEST',
     'os.environ["MOOR_HOME"] = x  # MOOR_TEST'),
    ('_MOOR_PROVIDER_ENV_FORCE_PREFIX = "_MOOR_FORCE_"',
     '_MOOR_PROVIDER_ENV_FORCE_PREFIX = "_MOOR_FORCE_"'),
    ("class MoorAgent(AIAgent): pass",
     "class MoorAgent(AIAgent): pass"),
    ("moor-agent==0.20.2 and moor-agent[cron]",
     "moor-agent==0.20.2 and moor-agent[cron]"),
    ('"Hey Moor" wake word hey_moor.onnx',
     '"Hey Moor" wake word hey_moor.onnx'),
    ("Moor inc. built this. Moor inc. org.",
     "Moor inc. built this. Moor inc. org."),
    ('name = "@moor/ink"; from "@moor/shared"',
     'name = "@moor/ink"; from "@moor/shared"'),
    ("MoorProfile uses moor_portal_tags and MOOR_TIMEOUT",
     "MoorProfile uses moor_portal_tags and MOOR_TIMEOUT"),
    ("the moor-agent project and moor-cli config",
     "the moor-agent project and moor-cli config"),
    ("scheme == 'moorroom' and pass:moorlocal",
     "scheme == 'moorroom' and pass:moorlocal"),
    ("run ('moorctl', 'serve') with smoora",
     "run ('moorctl', 'serve') with smoora"),
    ("MOORTEX sentinel: MOORTEXDISPLAY1MOORTEXEND",
     "MOORTEX sentinel: MOORTEXDISPLAY1MOORTEXEND"),
]

CASES_TRANSFORM = [
    ("scheme == 'hermesroom' and pass:hermeslocal",
     "scheme == 'moorroom' and pass:moorlocal"),
    ("run ('hermesctl', 'serve') with shermesa",
     "run ('moorctl', 'serve') with smoora"),
    ("token = 'HERMESTEXDISPLAY1HERMESTEXEND'",
     "token = 'MOORTEXDISPLAY1MOORTEXEND'"),
]

CASES_PROTECTED = [
    'base_url="https://inference-api.nousresearch.com/v1"',
    'PORTAL = "https://portal.nousresearch.com/oauth/authorize"',
    "models: NousResearch/Hermes-4-405B, openrouter/nousresearch/hermes-4-405b",
    'key = os.getenv("NOUS_API_KEY")',
    'fallback_models=("hermes-3-405b", "hermes-3-70b")',
    "Nous-Hermes-3 family and openrouter/hermes3",
    "image: nousresearch/hermes-agent:latest",
    "https://hermes-agent.nousresearch.com/docs/api/skills-index.json",
    "discord.gg/NousResearch",
    "github.com/NousResearch/hermes-example-plugins",
    "api.nous.test/v1 and https://nous.example/v1",
    "Hermes 3 and Hermes 4 chat families; FP16_Hermes_4.5",
    "expect(screen.getByText(/ares-3009\\.agents\\.nousresearch\\.com/i)).toBeTruthy()",
    "https://nousresearch.github.io/hermes-agent/docs/oauth/client-metadata.json",
    "https://nousresearch.github.io/hermes-agent/docs/img/logo.png",
]

CASES_DAMAGED = [
    ("https://inference-api.nousresearch.com/v1",
     "https://inference-api.nousresearch.com/v1"),
    ("com.moorinc.moor", "com.moorinc.moor"),
    ("NousResearch/Hermes-4-405B", "NousResearch/Hermes-4-405B"),
    ("support@nousresearch.com", "support@nousresearch.com"),
    ("image: NousResearch/hermes-agent:latest", "image: NousResearch/hermes-agent:latest"),
    ("moor-agent", "moor-agent"),
    ("hermes-agent.nousresearch...", "hermes-agent.nousresearch..."),
    ("https://nousresearch.github.io/hermes-agent/docs/oauth/client-metadata.json",
     "https://nousresearch.github.io/hermes-agent/docs/oauth/client-metadata.json"),
]

FORK_CASE = (
    "See https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/config.py "
    "and github.com/NousResearch/Hermes-Agent.git and github.com/NousResearch/hermes-agent/issues/1",
    "See https://github.com/acme/moor/blob/main/moor_cli/config.py "
    "and github.com/acme/moor.git and github.com/acme/moor/issues/1",
)

CASES_UPDATE_SOURCE = [
    # (rel, src, want): reinstall one-liners go GitHub-direct.
    ("moor_cli/update_cmd.py",
     "print(\"  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash\")",
     "print(\"  curl -fsSL https://raw.githubusercontent.com/thisismamad-n/Moor/master/scripts/install.sh | bash\")"),
    ("moor_cli/uninstall.py",
     "True: \"  iex (irm https://hermes-agent.nousresearch.com/install.ps1)\",",
     "True: \"  iex (irm https://raw.githubusercontent.com/thisismamad-n/Moor/master/scripts/install.ps1)\","),
    ("moor_cli/update_cmd_zip.py",
     "reinstall from https://hermes-agent.nousresearch.com",
     "reinstall from https://github.com/thisismamad-n/Moor"),
    ("moor_constants.py",
     "reinstall: https://hermes-agent.nousresearch.com",
     "reinstall: https://github.com/thisismamad-n/Moor"),
    ("moor_cli/update_cmd_deps.py",
     "print(\"    https://hermes-agent.nousresearch.com\")",
     "print(\"    https://github.com/thisismamad-n/Moor\")"),
    # Repo slugs and fallback branches keep rewriting.
    ("apps/desktop/electron/bootstrap-runner.ts",
     "const UPSTREAM_INSTALL_REPO = 'NousResearch/hermes-agent'",
     "const UPSTREAM_INSTALL_REPO = 'thisismamad-n/Moor'"),
    ("apps/desktop/electron/bootstrap-runner.ts",
     "const FALLBACK_BRANCH = 'main'",
     "const FALLBACK_BRANCH = 'master'"),
    # Docs URLs are protected even inside member files.
    ("moor_cli/update_cmd_maint.py",
     "print(\"  Docs:         https://hermes-agent.nousresearch.com/docs/user-guide/features/curator\")",
     "print(\"  Docs:         https://hermes-agent.nousresearch.com/docs/user-guide/features/curator\")"),
    # Non-member files are never touched.
    ("moor_cli/banner.py",
     "print(\"  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash\")",
     "print(\"  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash\")"),
    # Already-rebranded input is stable.
    ("moor_cli/update_cmd.py",
     "print(\"  curl -fsSL https://raw.githubusercontent.com/thisismamad-n/Moor/master/scripts/install.sh | bash\")",
     "print(\"  curl -fsSL https://raw.githubusercontent.com/thisismamad-n/Moor/master/scripts/install.sh | bash\")"),
]

PATH_CASES = [
    ("moor_cli/config.py", "moor_cli/config.py"),
    ("tests/moor_cli/test_moor_account.py", "tests/moor_cli/test_moor_account.py"),
    ("tools/wakewords/hey_moor.onnx", "tools/wakewords/hey_moor.onnx"),
    ("apps/desktop/src/types/moor.ts", "apps/desktop/src/types/moor.ts"),
    ("ui-tui/packages/moor-ink/index.js", "ui-tui/packages/moor-ink/index.js"),
    ("moor_constants.py", "moor_constants.py"),
    ("plugins/model-providers/moor/__init__.py", "plugins/model-providers/moor/__init__.py"),
]


def main() -> int:
    ok = fail = 0
    for src, want in CASES_PRISTINE:
        got = rb.transform_text(src, None)
        if got == want:
            ok += 1
        else:
            fail += 1
            print(f"FAIL pristine: {src!r}\n  got  {got!r}\n  want {want!r}")
    for src in CASES_PROTECTED:
        got = rb.transform_text(src, None)
        if got == src:
            ok += 1
        else:
            fail += 1
            print(f"FAIL protect: {src!r} -> {got!r}")
    for src, want in CASES_DAMAGED:
        got = rb.transform_text(src, None)
        if got == want:
            ok += 1
        else:
            fail += 1
            print(f"FAIL heal: {src!r}\n  got  {got!r}\n  want {want!r}")
    for src, want in CASES_TRANSFORM:
        got = rb.transform_text(src, None)
        if got == want:
            ok += 1
        else:
            fail += 1
            print(f"FAIL transform: {src!r}\n  got  {got!r}\n  want {want!r}")
    src, want = FORK_CASE
    got = rb.transform_text(src, "acme/moor")
    if got == want:
        ok += 1
    else:
        fail += 1
        print(f"FAIL fork:\n  got  {got!r}\n  want {want!r}")

    all_srcs = [s for s, _ in CASES_PRISTINE] + CASES_PROTECTED + [s for s, _ in CASES_DAMAGED]
    for s in all_srcs:
        once = rb.transform_text(s, "acme/moor")
        twice = rb.transform_text(once, "acme/moor")
        if once != twice:
            fail += 1
            print(f"FAIL idempotent: {once!r} -> {twice!r}")
    ok += len(all_srcs)

    for src, want in PATH_CASES:
        got = rb.rename_rel_path(src)
        if got == want:
            ok += 1
        else:
            fail += 1
            print(f"FAIL path: {src} -> {got} (want {want})")

    for rel, src, want in CASES_UPDATE_SOURCE:
        got = rb.transform_update_source(src, rel)
        if got == want:
            ok += 1
        else:
            fail += 1
            print(f"FAIL update-source [{rel}]: {src!r}\n  got  {got!r}\n  want {want!r}")
        twice = rb.transform_update_source(got, rel)
        if twice != got:
            fail += 1
            print(f"FAIL update-source idempotent [{rel}]: {got!r} -> {twice!r}")
        else:
            ok += 1

    # CLI branding preservation and legacy portal tags protection tests
    cli_protected = [
        "nous_portal_tags = moor_portal_tags  # LEGACY-PORTAL-TAGS: legacy provider alias",
        "nous_client_tag = moor_client_tag    # LEGACY-PORTAL-TAGS: legacy client tag alias",
    ]
    for line in cli_protected:
        got = rb.transform_text(line, None)
        if got == line:
            ok += 1
        else:
            fail += 1
            print(f"FAIL cli protected alias: {line!r} -> {got!r}")

    # phase_cli_branding must report 0 changes on an already-converged tree (idempotent)
    changes = rb.phase_cli_branding(dry=True)
    if not changes:
        ok += 1
    else:
        fail += 1
        print(f"FAIL phase_cli_branding not idempotent on converged tree: {changes}")

    # Verify canonical files on disk conform to Moor brand standards
    banner_text = (rb.REPO / "moor_cli" / "banner.py").read_text(encoding="utf-8")
    if "MOOR_ANT_HERO" in banner_text and "HERMES-AGENT" not in banner_text and "██╗  ██╗███████╗" not in banner_text:
        ok += 1
    else:
        fail += 1
        print("FAIL banner.py does not contain canonical MOOR and MOOR_ANT_HERO")

    skin_text = (rb.REPO / "moor_cli" / "skin_engine.py").read_text(encoding="utf-8")
    if "Cyber-Obsidian" in skin_text and "classic-gold" in skin_text and "Goodbye! ☤" not in skin_text:
        ok += 1
    else:
        fail += 1
        print("FAIL skin_engine.py does not contain Cyber-Obsidian and classic-gold skins")

    # Verify filler-bg0.jpg desktop backdrop asset override & storage
    if (
        "filler-bg0.jpg" in rb.ASSET_OVERRIDES
        and "apps/desktop/public/ds-assets/filler-bg0.jpg" in rb.ASSET_OVERRIDES["filler-bg0.jpg"]
        and (rb.REPO / "brand-assets" / "filler-bg0.jpg").is_file()
    ):
        ok += 1
    else:
        fail += 1
        print("FAIL filler-bg0.jpg missing from ASSET_OVERRIDES or brand-assets/")

    print(f"{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
