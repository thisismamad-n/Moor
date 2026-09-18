import shutil
import stat
import zipfile

import pytest

from moor_cli import main as moor_main
from moor_cli import update_source
from moor_cli.update_cmd_zip import _download_and_swap_zip


def _archive(tmp_path, monkeypatch, *, symlink=False):
    archive = tmp_path / "release.zip"
    root = tmp_path / "install"
    root.mkdir()
    (root / "existing.txt").write_text("keep", encoding="utf-8")
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Moor-master/pyproject.toml", '[project]\nname="moor-agent"\n[project.scripts]\nmoor="moor_cli.main:main"\n')
        for name in ("moor_cli/main.py", "moor_cli/update_source.py", "scripts/rebrand.py"):
            zf.writestr(f"Moor-master/{name}", "value = 1\n")
        zf.writestr("Moor-master/README.md", "ok\n")
        if symlink:
            info = zipfile.ZipInfo("Moor-master/link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, "README.md")
    monkeypatch.setattr(moor_main, "PROJECT_ROOT", root)
    monkeypatch.setattr(update_source, "download_archive", lambda branch, dest: shutil.copyfile(archive, dest))
    return root


def test_update_via_zip_rejects_symlink_member(tmp_path, monkeypatch, capsys):
    root = _archive(tmp_path, monkeypatch, symlink=True)
    with pytest.raises(SystemExit) as error:
        _download_and_swap_zip(update_source.BRANCH, f"https://api.github.com/repos/{update_source.REPO}/zipball/{update_source.BRANCH}")
    assert error.value.code == 1
    assert "symlink member" in capsys.readouterr().out
    assert not (root / "link").exists()
    assert not (root / "README.md").exists()
    assert (root / "existing.txt").read_text() == "keep"


def test_update_via_zip_accepts_normal_member(tmp_path, monkeypatch):
    root = _archive(tmp_path, monkeypatch)
    _download_and_swap_zip(update_source.BRANCH, f"https://api.github.com/repos/{update_source.REPO}/zipball/{update_source.BRANCH}")
    assert (root / "README.md").read_text() == "ok\n"
    assert (root / "existing.txt").read_text() == "keep"
