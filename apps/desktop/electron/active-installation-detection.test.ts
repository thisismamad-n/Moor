import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { test } from 'vitest'

import {
  launcherTargetsInstallation,
  resolveInstallationLauncher
} from './updater-process'
import { resolveSourceInstallationBackend } from './source-backend'

test('user-bin launchers are discovered without _launchers.py gating', (): void => {
  const base: string = fs.mkdtempSync(path.join(os.tmpdir(), 'moor-userbin-test-'))

  try {
    const root: string = path.join(base, 'moor-agent')
    const home: string = path.join(base, 'home')
    fs.mkdirSync(path.join(root, 'moor_cli'), { recursive: true })
    fs.writeFileSync(path.join(root, 'moor_cli', 'main.py'), '#!/usr/bin/env python3\n')
    // Crucially: no _launchers.py exists
    assert.equal(fs.existsSync(path.join(root, 'moor_cli', '_launchers.py')), false)

    fs.mkdirSync(path.join(home, 'bin'), { recursive: true })
    const launcherName = process.platform === 'win32' ? 'moor.cmd' : 'moor'
    const launcher: string = path.join(home, 'bin', launcherName)

    const body = (reported: string): string =>
      process.platform === 'win32'
        ? `@echo off\r\necho Install directory: ${reported}\r\n`
        : `#!/bin/sh\nprintf '%s\\n' 'Install directory: ${reported}'\n`

    fs.writeFileSync(launcher, body(root), { mode: 0o755 })
    assert.equal(launcherTargetsInstallation(launcher, root), true)

    const resolved = resolveInstallationLauncher(root, process.platform === 'win32', home)
    assert.equal(resolved, launcher)
  } finally {
    fs.rmSync(base, { recursive: true, force: true })
  }
})

test('resolveInstallationLauncher falls back to venv Scripts/bin if user-bin is absent', (): void => {
  const base: string = fs.mkdtempSync(path.join(os.tmpdir(), 'moor-venv-fallback-test-'))

  try {
    const root: string = path.join(base, 'moor-agent')
    const home: string = path.join(base, 'home')
    const venvBinDir: string = path.join(root, 'venv', process.platform === 'win32' ? 'Scripts' : 'bin')
    fs.mkdirSync(venvBinDir, { recursive: true })

    const launcherName = process.platform === 'win32' ? 'moor.exe' : 'moor'
    const venvLauncher: string = path.join(venvBinDir, launcherName)
    fs.writeFileSync(venvLauncher, 'placeholder', { mode: 0o755 })

    const resolved = resolveInstallationLauncher(root, process.platform === 'win32', home)
    assert.equal(resolved, venvLauncher)
  } finally {
    fs.rmSync(base, { recursive: true, force: true })
  }
})
