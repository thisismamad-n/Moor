# Offline & Local Installation Guide

This guide explains how to install the Moor Agent (CLI and Desktop App) entirely from this copied codebase on another computer.

## Prerequisites
Ensure the target computer has:
1. **Python 3.11+**
2. **Node.js** (required for the desktop app)
3. **uv** (a fast Python package manager). Install it via:
   - **Windows:** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - **macOS/Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## 1. Installing the CLI

To set up the CLI from this copied codebase, you need to create a virtual environment and install the package locally.

### macOS / Linux
You can simply run the provided setup script from the root of the codebase:
```bash
cd /path/to/copied/Moor
./setup-moor.sh
```
This script will automatically check/install `uv`, create a virtual environment, install dependencies, and symlink the `moor` command for you.

### Windows (PowerShell)
On Windows natively, set up the environment manually using `uv`:

```powershell
cd \path\to\copied\Moor

# 1. Create a virtual environment using Python 3.11
uv venv .venv --python 3.11

# 2. Activate the virtual environment
.venv\Scripts\activate

# 3. Install Moor and all required dependencies from the local directory
uv pip install -e ".[all]"
```
*(If you intend to work on the code, you can run `uv pip install -e ".[all,dev]"` instead).*

Once the installation finishes, you can start using the CLI:
```bash
# Run the first-time setup wizard
moor setup

# Start chatting!
moor
```

---

## 2. Installing the Desktop App

The Moor Desktop App is located in `apps/desktop`. You can either launch it directly from the CLI or build a standalone installer.

> **Offline-first builds:** every `.exe` produced by the 1-click compiler
> (`build-desktop-exe.bat`) or `npm run build` now ships the installer scripts
> (`install.ps1`/`install.sh`) **and** a full `repo.zip` of the Moor source
> tree *inside* the executable, so first launch needs no network to reach and
> pass the `repository` stage. See `OFFLINE_DESKTOP_BUNDLE.md` for the full
> architecture, what still needs the network on virgin machines, and how to
> verify an offline install.

### Method A: Launch directly (Recommended)
If you have installed the CLI (Step 1) and your `.venv` is activated, you can build and launch the Desktop UI with a single command:
```bash
moor desktop
```
*Note: This requires Node.js to be installed. It connects the native UI directly to your local configuration and sessions.*

### Method B: Build Standalone Installers
If you want to package the app into a shareable installer file (`.exe`, `.dmg`, `.AppImage`) so it can be installed permanently on the target machine:

1. From the **root** of the codebase, install the Node workspaces:
   ```bash
   npm install
   ```

2. Navigate to the desktop application directory:
   ```bash
   cd apps/desktop
   ```

3. Build the installer for the target operating system:
   ```bash
   npm run dist:win     # Builds Windows installers (.exe and MSI)
   npm run dist:mac     # Builds macOS installers (.dmg and .zip)
   npm run dist:linux   # Builds Linux installers (.AppImage, .deb, .rpm)
   ```

4. Once the build completes, the standalone installers will be available in the `apps/desktop/release/` directory.

---
### Troubleshooting
- **Missing CLI Commands:** If you can't run `moor` on Windows, ensure your virtual environment is activated (`.venv\Scripts\activate`).
- **Desktop Boot Issues:** If the desktop app fails to launch, check the boot logs located at `%LOCALAPPDATA%\moor\logs\desktop.log` (Windows) or `~/.moor/logs/desktop.log` (macOS/Linux).
