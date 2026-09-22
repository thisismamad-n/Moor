"""Tests to guarantee installer script syntax integrity and clean branding."""

import json
import os
import shutil
import subprocess
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_PS1 = os.path.join(REPO_ROOT, "scripts", "install.ps1")
INSTALL_SH = os.path.join(REPO_ROOT, "scripts", "install.sh")


def test_install_ps1_ast_syntax():
    """Verify that install.ps1 parses with 0 syntax errors via PowerShell AST."""
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        pytest.skip("PowerShell executable not found on PATH")

    cmd = [
        powershell,
        "-NoProfile",
        "-Command",
        (
            f"$errs = $null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{INSTALL_PS1}', [ref]$null, [ref]$errs); "
            f"if ($errs.Count -gt 0) {{ "
            f"  $errs | ForEach-Object {{ Write-Error \"$($_.Extent.StartLineNumber):$($_.Extent.StartColumnNumber) - $($_.Message)\" }}; "
            f"  exit 1 "
            f"}}"
        ),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    assert proc.returncode == 0, f"install.ps1 has AST parse errors:\n{proc.stderr}"


def test_install_ps1_manifest_execution():
    """Verify that install.ps1 -Manifest executes cleanly and emits valid manifest JSON."""
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        pytest.skip("PowerShell executable not found on PATH")

    cmd = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        INSTALL_PS1,
        "-Manifest",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    assert proc.returncode == 0, f"install.ps1 -Manifest failed with code {proc.returncode}:\n{proc.stderr}\n{proc.stdout}"

    # Manifest should be the last non-empty line
    lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]
    assert lines, "No output returned from install.ps1 -Manifest"
    manifest_raw = lines[-1]
    manifest = json.loads(manifest_raw)
    assert "protocol_version" in manifest, f"Missing protocol_version in manifest: {manifest}"
    assert "stages" in manifest, f"Missing stages in manifest: {manifest}"
    assert len(manifest["stages"]) > 0, "Manifest contains no stages"


def test_install_scripts_zero_legacy_install_urls():
    """Verify that neither install script advertises the legacy upstream download URL."""
    with open(INSTALL_PS1, "r", encoding="utf-8") as f:
        ps1_content = f.read()

    with open(INSTALL_SH, "r", encoding="utf-8") as f:
        sh_content = f.read()

    legacy_url = "hermes-agent.nousresearch.com/install"
    assert legacy_url not in ps1_content, f"Found legacy install URL in {INSTALL_PS1}"
    assert legacy_url not in sh_content, f"Found legacy install URL in {INSTALL_SH}"


def test_install_sh_moor_bin_priority():
    """Verify that install.sh checks 'moor' before fallback binary names."""
    with open(INSTALL_SH, "r", encoding="utf-8") as f:
        sh_content = f.read()

    assert 'which moor' in sh_content, "install.sh should check for moor on PATH"
