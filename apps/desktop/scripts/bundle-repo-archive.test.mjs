import assert from 'node:assert/strict'
import test from 'node:test'
import { collectRepoFiles } from './bundle-repo-archive.mjs'

test('collectRepoFiles includes essential source files', () => {
  const files = collectRepoFiles()
  const relPaths = new Set(files.map(f => f.relPath))

  assert.ok(relPaths.has('pyproject.toml'), 'should include pyproject.toml')
  assert.ok(relPaths.has('setup.py'), 'should include setup.py')
  assert.ok(relPaths.has('moor_bootstrap.py'), 'should include moor_bootstrap.py')
  assert.ok(relPaths.has('cli.py'), 'should include cli.py')
  assert.ok(relPaths.has('run_agent.py'), 'should include run_agent.py')
  assert.ok(relPaths.has('scripts/install.ps1'), 'should include scripts/install.ps1')

  // Check directories
  assert.ok(files.some(f => f.relPath.startsWith('agent/')), 'should include agent files')
  assert.ok(files.some(f => f.relPath.startsWith('moor_cli/')), 'should include moor_cli files')
  assert.ok(files.some(f => f.relPath.startsWith('tools/')), 'should include tools files')
  assert.ok(files.some(f => f.relPath.startsWith('gateway/')), 'should include gateway files')
  assert.ok(files.some(f => f.relPath.startsWith('skills/')), 'should include skills files')
})

test('collectRepoFiles excludes node_modules, venvs, and build artifacts', () => {
  const files = collectRepoFiles()

  for (const f of files) {
    assert.ok(!f.relPath.startsWith('node_modules/'), `should not contain node_modules: ${f.relPath}`)
    assert.ok(!f.relPath.startsWith('.venv/'), `should not contain .venv: ${f.relPath}`)
    assert.ok(!f.relPath.startsWith('venv/'), `should not contain venv: ${f.relPath}`)
    assert.ok(!f.relPath.startsWith('.git/'), `should not contain .git: ${f.relPath}`)
    assert.ok(!f.relPath.startsWith('.cache/'), `should not contain .cache: ${f.relPath}`)
    assert.ok(!f.relPath.startsWith('website/'), `should not contain website: ${f.relPath}`)
    assert.ok(!f.relPath.startsWith('apps/desktop/release/'), `should not contain desktop release: ${f.relPath}`)
    assert.ok(!f.relPath.endsWith('.pyc'), `should not contain .pyc: ${f.relPath}`)
  }
})
