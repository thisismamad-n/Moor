import { ipcMain } from 'electron'

import { type ChallengeWindowDependencies, createChallengeWindows, parseChallengeRequest } from './challenge-window'

/** The renderer's `moor:freeTierChallenge:run` invoke (preload `freeTierChallenge.run`). */
export function registerChallengeWindowIpc(dependencies: ChallengeWindowDependencies): void {
  const windows = createChallengeWindows(dependencies)

  ipcMain.handle('moor:freeTierChallenge:run', (_event, payload) => {
    const request = parseChallengeRequest(payload)

    return request ? windows.run(request) : 'refused'
  })
}
