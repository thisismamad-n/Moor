<#
.SYNOPSIS
    Compiles the native Windows desktop application executable (.exe) from the Moor codebase.

.DESCRIPTION
    Builds and packages the native Electron desktop application.
    Supports building:
      - installer: NSIS setup installer .exe (e.g. Moor-<version>-win-x64.exe)
      - portable:  Standalone portable .exe without setup wizard
      - unpacked:  Unpacked directory containing runnable Moor.exe
      - all:       Compiles installer, portable, and unpacked targets

    Zero Emojis Directive: All logging and output strictly adheres to ASCII formatting.

.PARAMETER Target
    Build target: 'installer' (default), 'portable', 'unpacked', or 'all'.

.PARAMETER Arch
    Target CPU architecture: 'x64' (default), 'arm64', or 'ia32'.

.PARAMETER Clean
    Cleans previous build output directories before compiling.

.PARAMETER SkipInstall
    Forces skipping npm install even if dependencies appear missing.

.PARAMETER OutputDir
    Custom output directory for compiled artifacts (defaults to apps/desktop/release).

.PARAMETER VerifyOnly
    Skips build and verifies already compiled .exe files in the output directory.

.EXAMPLE
    .\scripts\build-desktop-exe.ps1
    Compiles the default NSIS setup installer .exe (x64).

.EXAMPLE
    .\scripts\build-desktop-exe.ps1 -Target portable
    Compiles a standalone portable .exe.

.EXAMPLE
    .\scripts\build-desktop-exe.ps1 -Target all -Clean
    Cleans previous artifacts and compiles installer, portable, and unpacked outputs.

.EXAMPLE
    .\scripts\build-desktop-exe.ps1 -VerifyOnly
    Verifies PE headers and checksums of existing compiled executables.
#>

[CmdletBinding()]
param(
    [ValidateSet("installer", "portable", "unpacked", "all")]
    [string]$Target = "installer",

    [ValidateSet("x64", "arm64", "ia32")]
    [string]$Arch = "x64",

    [switch]$Clean,

    [switch]$SkipInstall,

    [string]$OutputDir = "",

    [switch]$VerifyOnly,

    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Get-Help $PSCommandPath -Detailed
    exit 0
}

# Disable strict npm engine enforcement to accommodate supported node minor versions (e.g. Node 22.14)
$env:npm_config_engine_strict = "false"
$env:NODE_OPTIONS = "--max-old-space-size=16384"

# --- Helper Logging Functions (Zero Emojis) ---
function Write-LogInfo([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-LogOk([string]$Message) {
    Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Write-LogWarn([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-LogError([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# --- Resolve Paths ---
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DesktopDir = Join-Path $ProjectRoot "apps\desktop"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $DesktopDir "release"
}

Write-LogInfo "Project Root: $ProjectRoot"
Write-LogInfo "Desktop Dir:  $DesktopDir"
Write-LogInfo "Output Dir:   $OutputDir"
Write-LogInfo "Target Mode:  $Target (arch: $Arch)"

# --- PE Header Binary Validation ---
function Test-PeExecutable([string]$FilePath, [string]$ExpectedArch = "x64") {
    if (-not (Test-Path -Path $FilePath -PathType Leaf)) {
        return @{ IsValid = $false; Error = "File does not exist: $FilePath" }
    }

    $FileItem = Get-Item $FilePath
    if ($FileItem.Length -lt 512) {
        return @{ IsValid = $false; Error = "File size too small for PE binary ($($FileItem.Length) bytes)" }
    }

    $Stream = [System.IO.File]::OpenRead($FilePath)
    $Reader = New-Object System.IO.BinaryReader($Stream)
    try {
        # DOS Header: MZ signature
        $Magic = $Reader.ReadBytes(2)
        if ($Magic.Length -lt 2 -or $Magic[0] -ne 0x4D -or $Magic[1] -ne 0x5A) {
            return @{ IsValid = $false; Error = "Missing DOS 'MZ' signature header" }
        }

        # Offset to PE Header (e_lfanew at offset 0x3C)
        $Stream.Seek(0x3C, [System.IO.SeekOrigin]::Begin) | Out-Null
        $PeOffset = $Reader.ReadInt32()
        if ($PeOffset -le 0 -or $PeOffset + 24 -gt $Stream.Length) {
            return @{ IsValid = $false; Error = "Corrupt DOS header: invalid e_lfanew offset" }
        }

        # PE Signature: "PE\0\0" (0x50, 0x45, 0x00, 0x00)
        $Stream.Seek($PeOffset, [System.IO.SeekOrigin]::Begin) | Out-Null
        $PeSig = $Reader.ReadBytes(4)
        if ($PeSig[0] -ne 0x50 -or $PeSig[1] -ne 0x45 -or $PeSig[2] -ne 0x00 -or $PeSig[3] -ne 0x00) {
            return @{ IsValid = $false; Error = "Missing 'PE\0\0' signature" }
        }

        # Machine and section count
        $Machine = $Reader.ReadUInt16()
        $Sections = $Reader.ReadUInt16()

        $MachineName = switch ($Machine) {
            0x8664 { "x64 (AMD64)" }
            0x014C { "x86 (32-bit)" }
            0xAA64 { "ARM64" }
            default { "Unknown (0x$($Machine.ToString('X4')))" }
        }

        $ValidForArch = switch ($ExpectedArch.ToLower()) {
            "x64"   { $Machine -eq 0x8664 -or $Machine -eq 0x014C }
            "arm64" { $Machine -eq 0xAA64 -or $Machine -eq 0x8664 }
            "ia32"  { $Machine -eq 0x014C }
            default { $true }
        }

        if (-not $ValidForArch) {
            return @{
                IsValid = $false
                Error = "Architecture mismatch: expected $ExpectedArch, binary is $MachineName"
            }
        }

        return @{
            IsValid = $true
            Machine = $MachineName
            Sections = $Sections
        }
    }
    catch {
        return @{ IsValid = $false; Error = $_.Exception.Message }
    }
    finally {
        $Reader.Close()
        $Stream.Close()
    }
}

# --- Discover Executables ---
function Get-CompiledExecutables([string]$Dir) {
    $Results = @()
    if (-not (Test-Path $Dir)) {
        return $Results
    }

    # Installer / portable .exe files
    $Exes = Get-ChildItem -Path $Dir -Filter "*.exe" -File -ErrorAction SilentlyContinue
    if ($Exes) {
        $Results += $Exes
    }

    # Unpacked directories with Moor.exe
    foreach ($Sub in @("win-unpacked", "win-ia32-unpacked", "win-arm64-unpacked")) {
        $UnpackedMoor = Join-Path $Dir "$Sub\Moor.exe"
        if (Test-Path $UnpackedMoor -PathType Leaf) {
            $Results += (Get-Item $UnpackedMoor)
        }
    }

    return $Results
}

# --- Print Summary ---
function Show-BuildSummary([array]$Executables, [string]$ExpectedArch) {
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor Gray
    Write-Host " DESKTOP APPLICATION COMPILATION SUMMARY" -ForegroundColor White
    Write-Host ("=" * 78) -ForegroundColor Gray

    if ($Executables.Count -eq 0) {
        Write-LogError "No executable files found in output directory."
        return $false
    }

    $AllValid = $true
    $Index = 1
    foreach ($Item in $Executables) {
        $Validation = Test-PeExecutable -FilePath $Item.FullName -ExpectedArch $ExpectedArch
        $SizeMB = [math]::Round($Item.Length / (1024 * 1024), 2)
        $Hash = (Get-FileHash -Path $Item.FullName -Algorithm SHA256).Hash

        $StatusTag = if ($Validation.IsValid) { "[OK]" } else { "[FAIL]" }
        $TagColor = if ($Validation.IsValid) { "Green" } else { "Red" }

        Write-Host ""
        Write-Host "$StatusTag Target #$Index`: $($Item.Name)" -ForegroundColor $TagColor
        Write-Host "  Path:        $($Item.FullName)" -ForegroundColor Gray
        Write-Host "  Size:        $SizeMB MB ($($Item.Length.ToString('N0')) bytes)" -ForegroundColor Gray
        if ($Validation.IsValid) {
            Write-Host "  PE Status:   $($Validation.Machine) ($($Validation.Sections) sections)" -ForegroundColor Gray
        } else {
            Write-Host "  PE Error:    $($Validation.Error)" -ForegroundColor Red
            $AllValid = $false
        }
        Write-Host "  SHA256:      $Hash" -ForegroundColor DarkGray
        $Index++
    }

    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor Gray
    if ($AllValid) {
        Write-LogOk "Executable compilation and PE validation completed successfully."
        Write-Host "Run the compiled executable directly or distribute the installer." -ForegroundColor Gray
    } else {
        Write-LogWarn "One or more compiled artifacts failed integrity verification."
    }
    Write-Host ("=" * 78) -ForegroundColor Gray
    Write-Host ""

    return $AllValid
}

# --- If VerifyOnly requested ---
if ($VerifyOnly) {
    Write-LogInfo "Running in verify-only mode..."
    $Found = Get-CompiledExecutables $OutputDir
    $Ok = Show-BuildSummary -Executables $Found -ExpectedArch $Arch
    if ($Ok) { exit 0 } else { exit 1 }
}

# --- Check Prerequisites ---
Write-LogInfo "Checking prerequisites..."

$NodeCmd = Get-Command "node" -ErrorAction SilentlyContinue
if (-not $NodeCmd) {
    Write-LogError "Node.js executable not found in PATH."
    exit 1
}

$NpmCmd = Get-Command "npm" -ErrorAction SilentlyContinue
if (-not $NpmCmd) {
    Write-LogError "npm executable not found in PATH."
    exit 1
}

$DesktopPackageJson = Join-Path $DesktopDir "package.json"
if (-not (Test-Path $DesktopPackageJson)) {
    Write-LogError "Desktop package.json missing at: $DesktopPackageJson"
    exit 1
}

Write-LogOk "Prerequisites verified (Node: $((& node -v)), npm: $((& npm -v)))"

# --- Stop File-Locking Processes ---
$RunningMoor = Get-Process -Name "Moor" -ErrorAction SilentlyContinue
if ($RunningMoor) {
    Write-LogWarn "Found running Moor desktop processes locking files. Terminating..."
    foreach ($p in $RunningMoor) {
        try {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            Write-LogInfo "Stopped process ID $($p.Id)"
        } catch {
            Write-LogWarn "Could not stop PID $($p.Id): $_"
        }
    }
    Start-Sleep -Seconds 1
}

# --- Clean Artifacts ---
if ($Clean) {
    Write-LogInfo "Cleaning previous build output..."
    $DistDir = Join-Path $DesktopDir "dist"
    if (Test-Path $DistDir) {
        Remove-Item -Path $DistDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    foreach ($Sub in @("win-unpacked", "win-ia32-unpacked", "win-arm64-unpacked")) {
        $Unp = Join-Path $OutputDir $Sub
        if (Test-Path $Unp) {
            Remove-Item -Path $Unp -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Write-LogOk "Clean complete"
}

# --- Ensure Dependencies ---
$RootNodeModules = Join-Path $ProjectRoot "node_modules"
$DesktopNodeModules = Join-Path $DesktopDir "node_modules"
$AssertScript = Join-Path $DesktopDir "scripts\assert-root-install.mjs"

$DepsValid = $false
if ((Test-Path $RootNodeModules) -and (Test-Path $DesktopNodeModules) -and (Test-Path $AssertScript)) {
    try {
        & node $AssertScript 2>$null
        if ($LASTEXITCODE -eq 0) {
            $DepsValid = $true
        }
    } catch {
        $DepsValid = $false
    }
}

if (-not $DepsValid) {
    if ($SkipInstall) {
        Write-LogWarn "Dependencies check failed but -SkipInstall was specified; proceeding anyway."
    } else {
        Write-LogInfo "Installing workspace dependencies (--engine-strict=false)..."
        Push-Location $ProjectRoot
        try {
            & npm install --workspace apps/desktop --engine-strict=false
            if ($LASTEXITCODE -ne 0) {
                Write-LogError "npm install failed with exit code $LASTEXITCODE"
                exit $LASTEXITCODE
            }
        } finally {
            Pop-Location
        }
        Write-LogOk "Workspace dependencies verified"
    }
} else {
    Write-LogOk "Workspace dependencies already installed and verified"
}

# --- Step 1: Compile Frontend & Electron Main ---
Write-LogInfo "Compiling desktop assets (Vite + Electron main + native dependencies)..."
Push-Location $DesktopDir
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-LogError "Frontend & Electron compilation failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
Write-LogOk "Frontend assets and Electron main bundle compiled successfully"

# --- Step 2: Package with electron-builder ---
$ArchFlag = "--$Arch"
$BuilderScript = Join-Path $DesktopDir "scripts\run-electron-builder.mjs"
$BuilderArgs = @()

if (-not [string]::IsNullOrWhiteSpace($OutputDir) -and $OutputDir -ne (Join-Path $DesktopDir "release")) {
    $BuilderArgs += "-c.directories.output=$OutputDir"
}

switch ($Target) {
    "installer" {
        $BuilderArgs += @("--win", "nsis", $ArchFlag)
    }
    "portable" {
        $BuilderArgs += @("--win", "portable", $ArchFlag)
    }
    "unpacked" {
        $BuilderArgs += @("--dir", $ArchFlag)
    }
    "all" {
        $BuilderArgs += @("--win", "nsis", "portable", $ArchFlag, "--dir")
    }
}

Write-LogInfo "Running electron-builder ($($BuilderArgs -join ' '))..."
Push-Location $DesktopDir
try {
    & node $BuilderScript @BuilderArgs
    if ($LASTEXITCODE -ne 0) {
        Write-LogError "electron-builder packaging failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

# --- Step 3: Discover & Validate Output Executables ---
$CompiledExecutables = Get-CompiledExecutables $OutputDir
$BuildSuccess = Show-BuildSummary -Executables $CompiledExecutables -ExpectedArch $Arch

if ($BuildSuccess) {
    exit 0
} else {
    exit 1
}
