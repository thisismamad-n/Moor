from pathlib import Path
import os
import shutil
import subprocess
import tomllib
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO = "thisismamad-n/Moor"
BRANCH = "master"
URL = f"https://github.com/{REPO}.git"


def _canonical(url: str) -> str:
    value = url.strip().removesuffix("/").removesuffix(".git").lower()
    if value.startswith("git@github.com:"):
        value = "github.com/" + value[len("git@github.com:"):]
    elif value.startswith("ssh://git@github.com/"):
        value = "github.com/" + value[len("ssh://git@github.com/"):]
    elif value.startswith("https://github.com/") or value.startswith("http://github.com/"):
        value = value.split("://", 1)[1]
    return value


def validate_source(url: str, branch: str) -> None:
    """Whether ``(url, branch)`` is the official Moor release source.

    Official-source predicate for the *download* path only (``download_archive``):
    the ZIP fallback always fetches from the official repo, never from a fork
    remote. It is NOT a gate on the local checkout — forks are a supported
    layout (``_is_fork``/upstream sync in ``update_cmd_git.py``), and ``--branch``
    explicitly targets non-default branches. Gating the checkout or the fetch
    target on this predicate would refuse legitimate fork checkouts and break
    ``--branch`` (the 20 ``test_cmd_update.py`` failures from the strict pin).
    Content authenticity of whatever was fetched is enforced by
    ``validate_update_tree`` instead.
    """
    if _canonical(url) != _canonical(URL):
        raise ValueError(f"Updates require origin={URL}. Repair the installation before updating.")
    if branch != BRANCH:
        raise ValueError(f"Moor updates require branch {BRANCH}.")


def validate_update_tree(read_text) -> None:
    """Fail closed with ``ValueError`` when the tree is not Moor content.

    Empty/malformed ``pyproject.toml`` is rejection, not a traceback:
    ``tomllib`` raises ``TOMLDecodeError`` on empty input and the
    ``["project"]`` lookup raises ``KeyError`` when the table is absent —
    both mean "not a Moor tree".
    """
    try:
        project = tomllib.loads(read_text("pyproject.toml"))["project"]
    except (tomllib.TOMLDecodeError, KeyError) as e:
        raise ValueError("Update rejected: package is not Moor.") from e
    if project.get("name") != "moor-agent" or "moor" not in project.get("scripts", {}):
        raise ValueError("Update rejected: package is not Moor.")
    for name in ("moor_cli/main.py", "scripts/rebrand.py", "moor_cli/update_source.py"):
        try:
            content = read_text(name)
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise ValueError(f"Update rejected: missing Moor component {name}.") from None
        if not content.strip():
            raise ValueError(f"Update rejected: missing Moor component {name}.")


class _MoorArchiveRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != "https" or target.netloc != "codeload.github.com" or not target.path.lower().startswith(f"/{REPO.lower()}/"):
            raise ValueError("Update rejected: unexpected archive redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_archive(branch: str, destination: str) -> None:
    validate_source(URL, branch)
    token = (os.environ.get("MOOR_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if any(char in token for char in "\r\n\0"):
        raise ValueError("Invalid update token.")
    request = Request(f"https://api.github.com/repos/{REPO}/zipball/{branch}", headers={"Accept": "application/vnd.github+json", "User-Agent": "Moor-Updater"})
    if token:
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    with build_opener(_MoorArchiveRedirect()).open(request, timeout=60) as response:
        with open(destination, "wb") as output:
            shutil.copyfileobj(response, output)


def validate_git_target(git_cmd, root: Path, branch: str) -> None:
    """Reject a fetched ``origin/<branch>`` tree whose content is not Moor.

    Branch-agnostic on purpose: ``--branch`` explicitly targets non-default
    branches, so pinning ``branch == BRANCH`` here would break the flag. The
    official-source URL check lives in ``download_archive`` (the ZIP path
    always downloads from the official repo); here only the *content* of
    whatever ref was fetched is authenticated.

    A missing ref (``git show`` exits non-zero) is NOT rejection: the
    downstream branch resolution reports it with the friendly "does not
    exist locally or on origin" error. Only an existing ref with wrong
    content is rejected here.
    """
    def read_text(name):
        return subprocess.run(
            [*git_cmd, "show", f"origin/{branch}:{name}"], cwd=root,
            capture_output=True, text=True, check=True,
        ).stdout
    try:
        validate_update_tree(read_text)
    except subprocess.CalledProcessError:
        return
