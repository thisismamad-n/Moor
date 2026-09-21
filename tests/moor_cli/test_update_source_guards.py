"""Moor-only update source guards: official-source predicate and content gates."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from moor_cli.update_source import (
    BRANCH,
    REPO,
    URL,
    validate_git_target,
    validate_source,
    validate_update_tree,
)

CANONICAL_URL = "https://github.com/thisismamad-n/Moor.git"
HERMES_URL = "https://github.com/NousResearch/hermes-agent.git"  # LEGACY-REBRAND-TEST: test fixture


def test_source_constants_are_the_moor_repo():
    assert REPO == "thisismamad-n/Moor"
    assert BRANCH == "master"
    assert URL == CANONICAL_URL


def test_validate_source_accepts_canonical_url_forms():
    validate_source("https://github.com/thisismamad-n/Moor.git", "master")
    validate_source("https://github.com/thisismamad-n/Moor", "master")
    validate_source("git@github.com:thisismamad-n/Moor.git", "master")
    validate_source("ssh://git@github.com/thisismamad-n/Moor.git", "master")
    validate_source(CANONICAL_URL, "master")


def test_validate_source_rejects_hermes_origin():  # LEGACY-REBRAND-TEST: guard test
    with pytest.raises(ValueError, match="Moor"):
        validate_source(HERMES_URL, "master")  # LEGACY-REBRAND-TEST: guard test


def test_validate_source_rejects_other_forks():
    with pytest.raises(ValueError, match="thisismamad-n/Moor"):
        validate_source("https://github.com/unrelated/moor.git", "master")


def test_validate_source_rejects_non_master_branches():
    with pytest.raises(ValueError, match="master"):
        validate_source(CANONICAL_URL, "main")


def test_resolve_update_branch_allows_custom_branches():
    """``--branch`` explicitly targets non-default branches; the resolver must
    not pin to master (that pin broke ``TestCmdUpdateBranchFlag``)."""
    from moor_cli.main_install_repair import _resolve_update_branch

    assert _resolve_update_branch(SimpleNamespace(branch="bb/gui")) == "bb/gui"
    assert _resolve_update_branch(SimpleNamespace(branch=None)) == "master"
    assert _resolve_update_branch(SimpleNamespace(branch="   ")) == "master"


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


MOOR_PYPROJECT = '[project]\nname = "moor-agent"\n\n[project.scripts]\nmoor = "moor_cli.main:main"\n'
HERMES_PYPROJECT = '[project]\nname = "hermes-agent"\n\n[project.scripts]\nhermes = "hermes_cli.main:main"\n'  # LEGACY-REBRAND-TEST: fixture


def test_validate_update_tree_accepts_moor_tree(tmp_path):
    _write_moor_tree(tmp_path)

    validate_update_tree(lambda name: (tmp_path / name).read_text(encoding="utf-8"))


def _write_moor_tree(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(MOOR_PYPROJECT, encoding="utf-8")
    _write_component_files(tmp_path)


def test_validate_update_tree_rejects_hermes_pyproject(tmp_path):  # LEGACY-REBRAND-TEST: guard test
    (tmp_path / "pyproject.toml").write_text(HERMES_PYPROJECT, encoding="utf-8")  # LEGACY-REBRAND-TEST: fixture
    _write_component_files(tmp_path)

    with pytest.raises(ValueError, match="not Moor"):
        validate_update_tree(lambda name: (tmp_path / name).read_text(encoding="utf-8"))


def _write_component_files(tmp_path: Path) -> None:
    for name in ("moor_cli/main.py", "scripts/rebrand.py", "moor_cli/update_source.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 1\n", encoding="utf-8")


def test_validate_update_tree_rejects_missing_components(tmp_path):
    (tmp_path / "pyproject.toml").write_text(MOOR_PYPROJECT, encoding="utf-8")
    for name in ("moor_cli/main.py", "scripts/rebrand.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing Moor component"):
        validate_update_tree(lambda name: (tmp_path / name).read_text(encoding="utf-8"))


def test_validate_git_target_reads_remote_tree(tmp_path):
    _git("init", "-q", cwd=tmp_path)
    _write_moor_tree(tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.name=T", "-c", "user.email=t@t", "commit", "-qm", "moor", cwd=tmp_path)
    _git("branch", "-M", "master", cwd=tmp_path)
    _git("remote", "add", "origin", CANONICAL_URL, cwd=tmp_path)
    _git("update-ref", "refs/remotes/origin/master", "HEAD", cwd=tmp_path)

    validate_git_target(["git"], tmp_path, "master")


def test_validate_git_target_rejects_hermes_remote_tree(tmp_path):  # LEGACY-REBRAND-TEST: guard test
    _git("init", "-q", cwd=tmp_path)
    (tmp_path / "pyproject.toml").write_text(HERMES_PYPROJECT, encoding="utf-8")  # LEGACY-REBRAND-TEST: fixture
    _write_component_files(tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "hermes", cwd=tmp_path)  # LEGACY-REBRAND-TEST: commit
    _git("branch", "-M", "master", cwd=tmp_path)
    _git("remote", "add", "origin", CANONICAL_URL, cwd=tmp_path)
    _git("update-ref", "refs/remotes/origin/master", "HEAD", cwd=tmp_path)

    with pytest.raises(ValueError, match="not Moor"):
        validate_git_target(["git"], tmp_path, "master")


def test_validate_git_target_supports_custom_branch(tmp_path):
    """The content gate is branch-agnostic so ``--branch`` keeps working."""
    _git("init", "-q", cwd=tmp_path)
    _write_moor_tree(tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.name=T", "-c", "user.email=t@t", "commit", "-qm", "moor", cwd=tmp_path)
    _git("branch", "-M", "bb/gui", cwd=tmp_path)
    _git("remote", "add", "origin", CANONICAL_URL, cwd=tmp_path)
    _git("update-ref", "refs/remotes/origin/bb/gui", "HEAD", cwd=tmp_path)

    validate_git_target(["git"], tmp_path, "bb/gui")
