from pathlib import Path
import subprocess
import tomllib

REPO = "thisismamad-n/Moor"
BRANCH = "master"
URL = f"https://github.com/{REPO}.git"


def validate_source(url: str, branch: str) -> None:
    if url.rstrip("/").removesuffix(".git").lower() != URL.removesuffix(".git").lower():
        raise ValueError(f"Updates require origin={URL}. Repair the installation before updating.")
    if branch != BRANCH:
        raise ValueError(f"Moor updates require branch {BRANCH}.")


def validate_checkout(root: Path, branch: str) -> None:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=root,
        capture_output=True, text=True, check=True,
    )
    validate_source(result.stdout.strip(), branch)


def validate_update_tree(read_text) -> None:
    project = tomllib.loads(read_text("pyproject.toml"))["project"]
    if project.get("name") != "moor-agent" or "moor" not in project.get("scripts", {}):
        raise ValueError("Update rejected: package is not Moor.")
    for name in ("moor_cli/main.py", "scripts/rebrand.py", "moor_cli/update_source.py"):
        if not read_text(name).strip():
            raise ValueError(f"Update rejected: missing Moor component {name}.")


def validate_git_target(git_cmd, root: Path, branch: str) -> None:
    validate_source(URL, branch)
    def read_text(name):
        return subprocess.run(
            [*git_cmd, "show", f"origin/{branch}:{name}"], cwd=root,
            capture_output=True, text=True, check=True,
        ).stdout
    validate_update_tree(read_text)
