#!/usr/bin/env python3
"""Build and compile the native Windows desktop application executable (.exe).

This script compiles the Electron desktop app from the Moor codebase.
Supported targets:
  - installer (default): Compiles an NSIS setup installer .exe (e.g. Moor-<version>-win-x64.exe)
  - portable: Compiles a standalone portable .exe without installation requirements
  - unpacked: Compiles an unpacked directory containing runnable Moor.exe
  - all: Compiles installer, portable, and unpacked versions

Zero Emojis Directive: All logging and UI text uses strict ASCII formatting.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# PE Machine Architecture Constants
PE_MACHINE_I386 = 0x014C
PE_MACHINE_AMD64 = 0x8664
PE_MACHINE_ARM64 = 0xAA64

PE_MACHINE_NAMES = {
    PE_MACHINE_I386: "x86 (32-bit)",
    PE_MACHINE_AMD64: "x64 (AMD64)",
    PE_MACHINE_ARM64: "ARM64",
}


def log_info(msg: str) -> None:
    """Print informational log line with ASCII indicator."""
    print(f"[INFO] {msg}")


def log_ok(msg: str) -> None:
    """Print success log line with ASCII indicator."""
    print(f"[OK] {msg}")


def log_warn(msg: str) -> None:
    """Print warning log line with ASCII indicator."""
    print(f"[WARN] {msg}")


def log_error(msg: str) -> None:
    """Print error log line with ASCII indicator."""
    print(f"[ERROR] {msg}")


def get_project_root() -> Path:
    """Resolve the repository root directory."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


def get_desktop_dir(project_root: Optional[Path] = None) -> Path:
    """Resolve the apps/desktop directory."""
    root = project_root or get_project_root()
    return root / "apps" / "desktop"


def parse_pe_header(exe_path: Path) -> Tuple[int, int]:
    """Parse the Windows PE header from an executable file.

    Returns:
        Tuple of (machine_type, number_of_sections).

    Raises:
        ValueError: If file is missing, too small, or not a valid PE binary.
    """
    if not exe_path.is_file():
        raise ValueError(f"Target executable does not exist: {exe_path}")

    file_size = exe_path.stat().st_size
    if file_size < 512:
        raise ValueError(
            f"File size is only {file_size} bytes, too small to be a Windows PE binary"
        )

    with exe_path.open("rb") as fh:
        dos_header = fh.read(64)
        if len(dos_header) < 64 or dos_header[:2] != b"MZ":
            raise ValueError(
                "Missing DOS MZ header signature; not a valid Windows executable"
            )

        (e_lfanew,) = struct.unpack_from("<I", dos_header, 0x3C)
        if e_lfanew <= 0 or e_lfanew + 24 > file_size:
            raise ValueError("Corrupt DOS header: e_lfanew points past EOF")

        fh.seek(e_lfanew)
        pe_sig = fh.read(4)
        if pe_sig != b"PE\x00\x00":
            raise ValueError("Missing PE signature header; binary is corrupt")

        coff_header = fh.read(20)
        if len(coff_header) < 20:
            raise ValueError("Truncated COFF header")

        machine, n_sections = struct.unpack_from("<HH", coff_header, 0)
        size_of_optional = struct.unpack_from("<H", coff_header, 16)[0]

        # Verify section boundaries
        fh.seek(e_lfanew + 24 + size_of_optional)
        max_section_end = 0
        for _ in range(n_sections):
            section_entry = fh.read(40)
            if len(section_entry) < 40:
                raise ValueError("Truncated PE section header table")
            size_of_raw, pointer_to_raw = struct.unpack_from(
                "<II", section_entry, 16
            )
            max_section_end = max(max_section_end, pointer_to_raw + size_of_raw)

        if file_size < max_section_end:
            raise ValueError(
                f"Truncated executable: file is {file_size} bytes but sections extend to {max_section_end} bytes"
            )

    return machine, n_sections


def verify_pe_executable(
    exe_path: Path, expected_arch: str = "x64"
) -> Tuple[bool, str]:
    """Verify that the compiled executable has valid PE structure and expected architecture.

    Returns:
        Tuple of (is_valid, description_or_error_message).
    """
    try:
        machine, sections = parse_pe_header(exe_path)
    except ValueError as exc:
        return False, str(exc)

    arch_map: Dict[str, Set[int]] = {
        "x64": {PE_MACHINE_AMD64, PE_MACHINE_I386},
        "arm64": {PE_MACHINE_ARM64, PE_MACHINE_AMD64},
        "ia32": {PE_MACHINE_I386},
    }
    allowed = arch_map.get(expected_arch.lower(), {PE_MACHINE_AMD64})
    if machine not in allowed:
        actual_name = PE_MACHINE_NAMES.get(machine, f"0x{machine:04X}")
        return (
            False,
            f"Architecture mismatch: expected {expected_arch}, but binary machine is {actual_name}",
        )

    arch_label = PE_MACHINE_NAMES.get(machine, "Unknown")
    return True, f"{arch_label} ({sections} sections)"


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def check_prerequisites(npm_executable: str = "npm") -> Tuple[bool, List[str]]:
    """Verify system prerequisites (Node.js, npm, package.json)."""
    errors: List[str] = []

    # Check Node.js
    node_bin = shutil.which("node")
    if not node_bin:
        errors.append("Node.js runtime not found in PATH")
    else:
        try:
            ver = subprocess.check_output(
                [node_bin, "--version"], text=True
            ).strip()
            # Expect v20+ or v22+
            major = int(ver.lstrip("v").split(".")[0])
            if major < 20:
                errors.append(
                    f"Node.js version {ver} is outdated; require v20 or later (v22+ recommended)"
                )
        except Exception as exc:
            errors.append(f"Failed to query Node.js version: {exc}")

    # Check npm
    npm_bin = shutil.which(npm_executable)
    if not npm_bin:
        errors.append(f"npm binary '{npm_executable}' not found in PATH")

    # Check workspace package.json
    root = get_project_root()
    desktop_pkg = root / "apps" / "desktop" / "package.json"
    if not desktop_pkg.is_file():
        errors.append(f"Desktop package.json missing at {desktop_pkg}")

    return len(errors) == 0, errors


def stop_locking_processes(desktop_dir: Path) -> List[int]:
    """Terminate running desktop instances that hold locks on the output directory on Windows."""
    if sys.platform != "win32":
        return []

    stopped: List[int] = []
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        # Fallback using tasklist/taskkill if psutil is unavailable
        return stop_locking_processes_taskkill()

    release_dir = (desktop_dir / "release").resolve()
    if not release_dir.is_dir():
        return []

    me = os.getpid()
    victims = []
    try:
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                info = proc.info
                pid = info.get("pid")
                exe = info.get("exe")
                name = info.get("name") or ""
                if not pid or pid == me:
                    continue
                if exe:
                    exe_path = Path(exe).resolve()
                    if release_dir in exe_path.parents or "Moor.exe" in exe_path.name:
                        victims.append(proc)
                elif "moor" in name.lower():
                    victims.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        return []

    for proc in victims:
        try:
            proc.terminate()
            stopped.append(int(proc.pid))
        except Exception:
            continue

    if stopped:
        try:
            _, alive = psutil.wait_procs(victims, timeout=5)
            for proc in alive:
                proc.kill()
        except Exception:
            pass

    return stopped


def stop_locking_processes_taskkill() -> List[int]:
    """Fallback lock release using Windows taskkill command."""
    if sys.platform != "win32":
        return []

    stopped: List[int] = []
    try:
        res = subprocess.run(
            ["taskkill", "/F", "/IM", "Moor.exe", "/T"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            log_info("Terminated existing Moor.exe processes via taskkill")
    except Exception:
        pass
    return stopped


def clean_artifacts(desktop_dir: Path, output_dir: Path) -> None:
    """Clean existing build directories and caches."""
    targets = [
        desktop_dir / "dist",
        output_dir / "win-unpacked",
        output_dir / "win-ia32-unpacked",
        output_dir / "win-arm64-unpacked",
    ]
    for target in targets:
        if target.is_dir():
            log_info(f"Removing build artifact directory: {target}")
            shutil.rmtree(target, ignore_errors=True)
        elif target.is_file():
            try:
                target.unlink()
            except OSError:
                pass


def ensure_workspace_deps(
    project_root: Path, npm_executable: str, skip_install: bool
) -> bool:
    """Ensure root and desktop workspace dependencies are installed."""
    desktop_node_modules = project_root / "apps" / "desktop" / "node_modules"
    root_node_modules = project_root / "node_modules"
    assert_script = (
        project_root / "apps" / "desktop" / "scripts" / "assert-root-install.mjs"
    )

    deps_valid = False
    if (
        desktop_node_modules.is_dir()
        and root_node_modules.is_dir()
        and assert_script.is_file()
    ):
        node_bin = shutil.which("node") or "node"
        res = subprocess.run(
            [node_bin, str(assert_script)],
            cwd=project_root / "apps" / "desktop",
            capture_output=True,
            check=False,
        )
        if res.returncode == 0:
            deps_valid = True

    if deps_valid:
        log_ok("Workspace dependencies already installed and verified")
        return True

    if skip_install:
        log_warn("Dependencies check failed but skip_install was specified; proceeding anyway.")
        return True

    log_info("Installing desktop workspace dependencies (--engine-strict=false)...")
    env = os.environ.copy()
    env["npm_config_engine_strict"] = "false"
    cmd = [
        npm_executable,
        "install",
        "--workspace",
        "apps/desktop",
        "--engine-strict=false",
    ]
    res = subprocess.run(cmd, cwd=project_root, env=env, check=False)
    if res.returncode != 0:
        log_error(f"npm install failed with exit code {res.returncode}")
        return False
    log_ok("Workspace dependencies verified")
    return True


def run_desktop_build(desktop_dir: Path, npm_executable: str) -> bool:
    """Compile the renderer assets, main process, and native bindings."""
    log_info("Compiling desktop assets (Vite + Electron Main + Native Staging)...")
    env = os.environ.copy()
    env["NODE_OPTIONS"] = "--max-old-space-size=16384"
    env["npm_config_engine_strict"] = "false"

    cmd = [npm_executable, "run", "build"]
    res = subprocess.run(cmd, cwd=desktop_dir, env=env, check=False)
    if res.returncode != 0:
        log_error(f"Frontend and Electron build failed with code {res.returncode}")
        return False
    return True


def resolve_builder_arguments(
    target: str, arch: str, output_dir: Path
) -> List[str]:
    """Resolve electron-builder CLI arguments for the specified target and architecture."""
    args: List[str] = []
    # Only add custom output dir if non-default
    default_output = get_desktop_dir() / "release"
    if output_dir.resolve() != default_output.resolve():
        args.append(f"-c.directories.output={output_dir}")

    arch_flag = f"--{arch}" if arch in ("x64", "arm64", "ia32") else "--x64"

    if target == "installer":
        args.extend(["--win", "nsis", arch_flag])
    elif target == "portable":
        args.extend(["--win", "portable", arch_flag])
    elif target == "unpacked":
        args.extend(["--dir", arch_flag])
    elif target == "all":
        args.extend(["--win", "nsis", "portable", arch_flag, "--dir"])
    else:
        # Default fallback to installer
        args.extend(["--win", "nsis", arch_flag])

    return args


def run_electron_builder(
    desktop_dir: Path, npm_executable: str, builder_args: List[str]
) -> bool:
    """Execute electron-builder packaging with configured arguments."""
    log_info(
        f"Packaging executable with electron-builder: {' '.join(builder_args)}"
    )
    env = os.environ.copy()
    env["NODE_OPTIONS"] = "--max-old-space-size=16384"
    env["npm_config_engine_strict"] = "false"

    builder_script = desktop_dir / "scripts" / "run-electron-builder.mjs"
    node_bin = shutil.which("node") or "node"
    cmd = [node_bin, str(builder_script), *builder_args]
    res = subprocess.run(cmd, cwd=desktop_dir, env=env, check=False)
    if res.returncode != 0:
        log_error(f"electron-builder packaging failed with code {res.returncode}")
        return False
    return True


def locate_compiled_executables(
    output_dir: Path, target: str
) -> List[Path]:
    """Discover compiled .exe files in the output directory according to target."""
    found: List[Path] = []

    if not output_dir.is_dir():
        return found

    # Scan for top-level installer or portable .exe files
    for exe in output_dir.glob("*.exe"):
        if exe.is_file():
            found.append(exe)

    # Scan for unpacked Moor.exe
    for unpacked_dir_name in (
        "win-unpacked",
        "win-ia32-unpacked",
        "win-arm64-unpacked",
    ):
        unpacked_exe = output_dir / unpacked_dir_name / "Moor.exe"
        if unpacked_exe.is_file():
            found.append(unpacked_exe)

    # Deduplicate while preserving order
    seen: Set[Path] = set()
    unique: List[Path] = []
    for item in found:
        resolved = item.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(item)

    return unique


def print_build_summary(
    executables: List[Path], expected_arch: str
) -> bool:
    """Print ASCII summary of all compiled executables with verification status."""
    print("\n" + "=" * 78)
    print(" DESKTOP APPLICATION COMPILATION SUMMARY")
    print("=" * 78)

    if not executables:
        log_error("No executable files were located in the output directory.")
        return False

    all_valid = True
    for idx, exe in enumerate(executables, 1):
        rel_path = (
            exe.relative_to(get_project_root())
            if exe.is_relative_to(get_project_root())
            else exe
        )
        size_mb = exe.stat().st_size / (1024 * 1024)
        is_valid, status = verify_pe_executable(exe, expected_arch=expected_arch)
        sha = calculate_sha256(exe)

        status_tag = "[OK]" if is_valid else "[FAIL]"
        if not is_valid:
            all_valid = False

        print(f"\n{status_tag} Target #{idx}: {exe.name}")
        print(f"  Path:        {rel_path}")
        print(f"  Size:        {size_mb:.2f} MB ({exe.stat().st_size:,} bytes)")
        print(f"  PE Status:   {status}")
        print(f"  SHA256:      {sha}")

    print("\n" + "=" * 78)
    if all_valid:
        log_ok("Executable compilation and PE validation completed successfully.")
        print("Run the compiled executable directly or distribute the installer.")
    else:
        log_warn("One or more compiled artifacts failed integrity verification.")
    print("=" * 78 + "\n")

    return all_valid


def main() -> int:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Compile native Windows desktop application executable (.exe) from Moor codebase.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--target",
        choices=["installer", "portable", "unpacked", "all"],
        default="installer",
        help="Build target: 'installer' (NSIS setup .exe), 'portable' (standalone .exe), 'unpacked' (directory), or 'all'",
    )
    parser.add_argument(
        "--arch",
        choices=["x64", "arm64", "ia32"],
        default="x64",
        help="Target CPU architecture",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean previous build artifacts before compiling",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip npm dependency installation check if node_modules exist",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Custom output directory for compiled artifacts (defaults to apps/desktop/release)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip compilation and verify already compiled executables in output directory",
    )
    parser.add_argument(
        "--npm",
        default="npm",
        help="npm binary name or path",
    )

    args = parser.parse_args()

    project_root = get_project_root()
    desktop_dir = get_desktop_dir(project_root)
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else (desktop_dir / "release").resolve()
    )

    log_info(f"Project Root: {project_root}")
    log_info(f"Desktop Dir:  {desktop_dir}")
    log_info(f"Output Dir:   {output_dir}")
    log_info(f"Target Mode:  {args.target} (arch: {args.arch})")

    # If verify-only requested, locate and verify
    if args.verify_only:
        log_info("Running in verify-only mode...")
        executables = locate_compiled_executables(output_dir, args.target)
        success = print_build_summary(executables, expected_arch=args.arch)
        return 0 if success else 1

    # Check prerequisites
    ok, errors = check_prerequisites(npm_executable=args.npm)
    if not ok:
        log_error("Prerequisites check failed:")
        for err in errors:
            print(f"  - {err}")
        return 1
    log_ok("Prerequisites verified (Node.js, npm, package.json)")

    # Stop file-locking processes on Windows
    stopped_pids = stop_locking_processes(desktop_dir)
    if stopped_pids:
        log_warn(
            f"Stopped {len(stopped_pids)} process(es) locking build output: {stopped_pids}"
        )

    # Clean previous artifacts if requested
    if args.clean:
        clean_artifacts(desktop_dir, output_dir)
        log_ok("Cleaned previous build artifacts")

    # Ensure dependencies
    if not ensure_workspace_deps(
        project_root, args.npm, skip_install=args.skip_install
    ):
        return 1

    # Build frontend bundle and electron main
    if not run_desktop_build(desktop_dir, args.npm):
        return 1
    log_ok("Frontend assets and Electron main bundle built successfully")

    # Run electron-builder packaging
    builder_args = resolve_builder_arguments(
        args.target, args.arch, output_dir
    )
    if not run_electron_builder(desktop_dir, args.npm, builder_args):
        return 1

    # Locate and verify output executables
    executables = locate_compiled_executables(output_dir, args.target)
    success = print_build_summary(executables, expected_arch=args.arch)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
