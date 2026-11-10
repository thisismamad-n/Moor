import { describe, expect, it } from 'vitest'

import { commandLineIsMoorRuntime } from './moor-process'

// HX003: process identity comes from a whole argv TOKEN, never an argv substring.
describe('commandLineIsMoorRuntime (HX003 token matching)', () => {
  it('matches a real Moor gateway command line', () => {
    expect(commandLineIsMoorRuntime('moor\0gateway\0run')).toBe(true)
    expect(commandLineIsMoorRuntime('moor gateway run')).toBe(true)
    expect(commandLineIsMoorRuntime('moor --profile work gateway run')).toBe(true)
  })

  it('matches a Moor launched by an interpreter (basename of a path token)', () => {
    expect(commandLineIsMoorRuntime('/venv/bin/python\0/venv/bin/moor\0gateway\0run')).toBe(true)
    expect(commandLineIsMoorRuntime('C:\\Moor\\moor.exe gateway run')).toBe(true)
  })

  // The bug this replaces: a bare `.includes('moor')` matched any of these.
  it('does NOT match an unrelated process whose path merely contains "moor"', () => {
    expect(commandLineIsMoorRuntime('vim /home/user/moor-notes.txt')).toBe(false)
    expect(commandLineIsMoorRuntime('/opt/hermesbrew/bin/tool --run')).toBe(false)  // LEGACY-REBRAND-TEST: negative match against legacy path
    expect(commandLineIsMoorRuntime('node /srv/moor-dashboard/server.js')).toBe(false)
    expect(commandLineIsMoorRuntime('cat ~/.moor/config.yaml')).toBe(false)
  })

  // G2 (#150283): the real unmanaged-gateway launch is `python -m moor_cli.main … gateway
  // run`, which the executable-basename-only matcher REJECTED — so findRunningGatewayProfiles
  // missed a live gateway at first launch / profile repair. Mirror the canonical Python matcher
  // (gateway.status.looks_like_gateway_command_line): recognize the module entry point, by argv
  // TOKENS not a substring, carrying the gateway subcommand.
  it('matches a module-launched gateway (python -m moor_cli.main … gateway run)', () => {
    expect(commandLineIsMoorRuntime('python\0-m\0moor_cli.main\0-p\0x\0gateway\0run')).toBe(true)
    expect(commandLineIsMoorRuntime('python -m moor_cli.main -p x gateway run')).toBe(true)
    expect(commandLineIsMoorRuntime('/venv/bin/python /venv/lib/moor_cli/main.py gateway run')).toBe(true)
    expect(commandLineIsMoorRuntime('python -m moor_cli.main --profile work gateway run')).toBe(true)
  })

  it('does NOT match a module entry without the gateway subcommand, nor an unrelated moor-tool path', () => {
    // A moor_cli.main invocation that is not a gateway (e.g. `chat`) is not a running gateway.
    expect(commandLineIsMoorRuntime('python -m moor_cli.main chat')).toBe(false)
    // HX003: no substring; an unrelated tool whose path contains "moor" is never a runtime.
    expect(commandLineIsMoorRuntime('/opt/moor-tool/foo gateway run')).toBe(false)
    // `-p gateway` is a profile value, not a subcommand.
    expect(commandLineIsMoorRuntime('python -m moor_cli.main -p gateway chat')).toBe(false)
  })
})
