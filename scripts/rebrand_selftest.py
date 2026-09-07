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
]

CASES_TRANSFORM = [
    ("scheme == 'hermesroom' and pass:hermeslocal",
     "scheme == 'moorroom' and pass:moorlocal"),
    ("run ('hermesctl', 'serve') with shermesa",
     "run ('moorctl', 'serve') with smoora"),
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

    print(f"{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
