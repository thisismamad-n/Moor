from pathlib import Path


def test_windows_native_install_path_docs_match_installer() -> None:
    doc = Path("website/docs/user-guide/windows-native.md").read_text()
    install = Path("scripts/install.ps1").read_text()

    # The launchers live in the managed binary dir OUTSIDE the git checkout
    # (MOOR_HOME\bin, next to the managed uv) — NOT the whole venv\Scripts
    # (which would shadow the user's python, #83797) and NOT a dir inside
    # the checkout (which `moor update`'s autostash swept off disk).
    assert "%LOCALAPPDATA%\\moor\\bin" in doc
    assert (
        "Get-Command moor        # should print "
        "C:\\Users\\<you>\\AppData\\Local\\moor\\bin\\moor.exe"
    ) in doc
    # Installer exposes $MoorHome\bin, and must copy the launchers into it.
    assert '$moorBin = "$MoorHome\\bin"' in install
    assert "moor.exe" in install and "moor-acp.exe" in install
    # Guard against regressions to either legacy layout.
    assert '$moorBin = "$InstallDir\\venv\\Scripts"' not in install
    assert '$moorBin = "$InstallDir\\bin"' not in install
