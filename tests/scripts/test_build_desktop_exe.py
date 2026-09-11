"""Unit tests for scripts/build_desktop_exe.py."""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import module under test
import scripts.build_desktop_exe as bde


def create_synthetic_pe(
    machine: int = bde.PE_MACHINE_AMD64,
    n_sections: int = 1,
    section_raw_size: int = 512,
) -> bytes:
    """Helper to create a valid minimal Windows PE byte sequence for unit testing."""
    # DOS Header: 64 bytes, starting with 'MZ' and e_lfanew at 0x3C pointing to 0x80
    dos_header = bytearray(b"MZ" + b"\x00" * 62)
    e_lfanew = 0x80
    struct.pack_into("<I", dos_header, 0x3C, e_lfanew)

    # Pad until e_lfanew
    pad_to_pe = b"\x00" * (e_lfanew - len(dos_header))

    # PE Signature: 'PE\0\0' (4 bytes)
    pe_sig = b"PE\x00\x00"

    # COFF Header: 20 bytes
    # machine (2), n_sections (2), time (4), ptr_sym (4), n_sym (4), size_opt (2), characteristics (2)
    size_of_optional = 0
    coff_header = struct.pack(
        "<HHIIIHH",
        machine,
        n_sections,
        0x12345678,
        0,
        0,
        size_of_optional,
        0x0002,  # IMAGE_FILE_EXECUTABLE_IMAGE
    )

    # Section Headers: 40 bytes each
    # name (8), virtual_size (4), virtual_address (4), raw_size (4), raw_ptr (4)...
    header_end = e_lfanew + 4 + 20 + size_of_optional + (n_sections * 40)
    raw_ptr = (header_end + 511) // 512 * 512  # Align to 512

    sections_data = bytearray()
    for i in range(n_sections):
        sec = bytearray(40)
        sec[0:5] = f".sec{i}".encode("ascii")
        struct.pack_into("<II", sec, 16, section_raw_size, raw_ptr)
        sections_data.extend(sec)

    # Section Payload
    payload_end = raw_ptr + section_raw_size
    full_length = payload_end
    binary = (
        dos_header
        + pad_to_pe
        + pe_sig
        + coff_header
        + sections_data
    )
    if len(binary) < raw_ptr:
        binary += b"\x00" * (raw_ptr - len(binary))
    binary += b"\x90" * section_raw_size  # NOP instructions
    return bytes(binary)


class TestPEValidation:
    """Tests for PE header inspection and integrity checking."""

    def test_missing_file_raises(self, tmp_path: Path):
        non_existent = tmp_path / "missing.exe"
        with pytest.raises(ValueError, match="does not exist"):
            bde.parse_pe_header(non_existent)

    def test_file_too_small_raises(self, tmp_path: Path):
        small = tmp_path / "tiny.exe"
        small.write_bytes(b"MZ" + b"\x00" * 100)
        with pytest.raises(ValueError, match="too small"):
            bde.parse_pe_header(small)

    def test_missing_mz_signature_raises(self, tmp_path: Path):
        bad_magic = tmp_path / "bad.exe"
        bad_magic.write_bytes(b"PK" + b"\x00" * 600)
        with pytest.raises(ValueError, match="Missing DOS MZ header"):
            bde.parse_pe_header(bad_magic)

    def test_corrupt_e_lfanew_raises(self, tmp_path: Path):
        corrupt = tmp_path / "corrupt.exe"
        data = bytearray(b"MZ" + b"\x00" * 600)
        struct.pack_into("<I", data, 0x3C, 999999)  # Points past EOF
        corrupt.write_bytes(data)
        with pytest.raises(ValueError, match="points past EOF"):
            bde.parse_pe_header(corrupt)

    def test_missing_pe_sig_raises(self, tmp_path: Path):
        bad_pe = tmp_path / "bad_pe.exe"
        data = bytearray(b"MZ" + b"\x00" * 600)
        struct.pack_into("<I", data, 0x3C, 0x80)
        data[0x80:0x84] = b"NOTP"
        bad_pe.write_bytes(data)
        with pytest.raises(ValueError, match="Missing PE signature"):
            bde.parse_pe_header(bad_pe)

    def test_valid_synthetic_pe_amd64(self, tmp_path: Path):
        valid = tmp_path / "valid.exe"
        valid.write_bytes(create_synthetic_pe(bde.PE_MACHINE_AMD64))
        machine, sections = bde.parse_pe_header(valid)
        assert machine == bde.PE_MACHINE_AMD64
        assert sections == 1

        is_valid, msg = bde.verify_pe_executable(valid, expected_arch="x64")
        assert is_valid is True
        assert "x64 (AMD64)" in msg

    def test_valid_synthetic_pe_arm64(self, tmp_path: Path):
        valid = tmp_path / "valid_arm64.exe"
        valid.write_bytes(create_synthetic_pe(bde.PE_MACHINE_ARM64))
        is_valid, msg = bde.verify_pe_executable(valid, expected_arch="arm64")
        assert is_valid is True
        assert "ARM64" in msg

    def test_pe_arch_mismatch(self, tmp_path: Path):
        arm_pe = tmp_path / "arm.exe"
        arm_pe.write_bytes(create_synthetic_pe(bde.PE_MACHINE_ARM64))
        is_valid, msg = bde.verify_pe_executable(arm_pe, expected_arch="ia32")
        assert is_valid is False
        assert "Architecture mismatch" in msg

    def test_real_python_pe_if_on_windows(self):
        """On Windows, verify that sys.executable parses as a valid PE binary."""
        if sys.platform != "win32":
            pytest.skip("Windows only test")
        exe = Path(sys.executable)
        is_valid, desc = bde.verify_pe_executable(exe, expected_arch="x64")
        assert is_valid is True
        assert "x64" in desc or "AMD64" in desc or "sections" in desc


class TestBuilderArguments:
    """Tests for electron-builder CLI argument generation."""

    def test_installer_target(self, tmp_path: Path):
        args = bde.resolve_builder_arguments("installer", "x64", tmp_path)
        assert "--win" in args
        assert "nsis" in args
        assert "--x64" in args
        assert f"-c.directories.output={tmp_path}" in args

    def test_portable_target(self, tmp_path: Path):
        args = bde.resolve_builder_arguments("portable", "arm64", tmp_path)
        assert "--win" in args
        assert "portable" in args
        assert "--arm64" in args

    def test_unpacked_target(self, tmp_path: Path):
        args = bde.resolve_builder_arguments("unpacked", "x64", tmp_path)
        assert "--dir" in args
        assert "--x64" in args

    def test_all_target(self, tmp_path: Path):
        args = bde.resolve_builder_arguments("all", "x64", tmp_path)
        assert "nsis" in args
        assert "portable" in args
        assert "--dir" in args


class TestFileDiscoveryAndHashing:
    """Tests for executable discovery and SHA256 checksums."""

    def test_calculate_sha256(self, tmp_path: Path):
        sample = tmp_path / "sample.bin"
        content = b"Moor Desktop Application Test Data"
        sample.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert bde.calculate_sha256(sample) == expected

    def test_locate_compiled_executables(self, tmp_path: Path):
        # Empty dir
        assert bde.locate_compiled_executables(tmp_path, "all") == []

        # Add root installer
        installer = tmp_path / "Moor-0.17.0-win-x64.exe"
        installer.write_bytes(b"installer content")

        # Add unpacked Moor.exe
        unpacked_dir = tmp_path / "win-unpacked"
        unpacked_dir.mkdir(parents=True)
        unpacked_exe = unpacked_dir / "Moor.exe"
        unpacked_exe.write_bytes(b"unpacked content")

        found = bde.locate_compiled_executables(tmp_path, "all")
        assert len(found) == 2
        names = [f.name for f in found]
        assert "Moor-0.17.0-win-x64.exe" in names
        assert "Moor.exe" in names


class TestPrerequisitesAndCleaning:
    """Tests for prerequisite checks and cleaning artifacts."""

    @patch("shutil.which")
    def test_missing_node_reports_error(self, mock_which):
        mock_which.return_value = None
        ok, errors = bde.check_prerequisites("npm")
        assert ok is False
        assert any("Node.js" in e for e in errors)

    def test_clean_artifacts(self, tmp_path: Path):
        desktop = tmp_path / "desktop"
        output = tmp_path / "release"
        dist = desktop / "dist"
        unpacked = output / "win-unpacked"

        dist.mkdir(parents=True)
        unpacked.mkdir(parents=True)
        (dist / "index.html").write_text("ok")
        (unpacked / "Moor.exe").write_bytes(b"exe")

        assert dist.exists()
        assert unpacked.exists()

        bde.clean_artifacts(desktop, output)

        assert not dist.exists()
        assert not unpacked.exists()


class TestBatchLauncher:
    """Tests verifying the Windows .bat launchers."""

    def test_root_batch_file_exists_and_references_ps1(self):
        root = bde.get_project_root()
        bat = root / "build-desktop-exe.bat"
        assert bat.is_file()
        content = bat.read_text(encoding="utf-8", errors="ignore")
        assert "build-desktop-exe.ps1" in content
        assert "pwsh" in content
        assert "pause" in content

    def test_scripts_batch_forwarder_exists(self):
        root = bde.get_project_root()
        script_bat = root / "scripts" / "build-desktop-exe.bat"
        assert script_bat.is_file()
        content = script_bat.read_text(encoding="utf-8", errors="ignore")
        assert "build-desktop-exe.bat" in content

