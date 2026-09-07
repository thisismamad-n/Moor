import { contextBridge, ipcRenderer, webFrame, webUtils } from 'electron'

// Which translucency the OS can back. Asked synchronously because the renderer
// needs it before its first paint, and answered by main because deciding it
// needs `os.release()` — a sandboxed preload may only require electron, events,
// timers and url, so importing node:os here throws before contextBridge runs
// and takes the ENTIRE bridge down with it (window.moorDesktop undefined =>
// "Desktop IPC bridge is unavailable"). No reply means no glass, which degrades
// to an ordinary opaque window rather than a page thinned over nothing.
const translucencySupport = ipcRenderer.sendSync('moor:translucency:support')
const hudWindowing = ipcRenderer.sendSync('moor:hud:windowing')
const hudNativeDrag = hudWindowing?.nativeDrag === true
const launchFlags = ipcRenderer.sendSync('moor:launch-flags')

contextBridge.exposeInMainWorld('moorDesktop', {
  glassSupported: translucencySupport?.glass === true,
  translucencySupported: translucencySupport?.translucency === true,
  // Launch-flag fact: the app was started with --local, so the renderer may
  // show the local-models surfaces. Static for the window's lifetime.
  localModelsEnabled: launchFlags?.localModels === true,
  getConnection: (profile, opts) => ipcRenderer.invoke('moor:connection', profile, opts),
  // Registry-scoped backend resolution: { connectionId, profile } → descriptor.
  getConnectionFor: payload => ipcRenderer.invoke('moor:connection:for', payload),
  getProfileRoutes: profiles => ipcRenderer.invoke('moor:plugin-profile-routes', profiles),
  revalidateConnection: () => ipcRenderer.invoke('moor:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('moor:backend:touch', profile),
  getPoolLimits: () => ipcRenderer.invoke('moor:pool-limits:get'),
  setPoolLimits: limits => ipcRenderer.invoke('moor:pool-limits:set', limits),
  getGatewayWsUrl: profile => ipcRenderer.invoke('moor:gateway:ws-url', profile),
  // Registry-scoped fresh WS URL: { connectionId, profile } → result shape of
  // getGatewayWsUrl, minted against that connection's backend.
  getGatewayWsUrlFor: payload => ipcRenderer.invoke('moor:gateway:ws-url-for', payload),
  // Union agent roster across every registered connection.
  getAgentRoster: () => ipcRenderer.invoke('moor:agents:roster'),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('moor:window:openSession', sessionId, opts),
  openSessionInTerminal: (sessionId, opts) => ipcRenderer.invoke('moor:window:openInTerminal', sessionId, opts),
  openWindow: () => ipcRenderer.invoke('moor:window:openInstance'),
  openBrowserWindow: tabId => ipcRenderer.invoke('moor:window:openBrowser', tabId),
  onBrowserPopoutClosed: callback => {
    const listener = (_event, tabId) => callback(tabId)
    ipcRenderer.on('moor:browser-popout:closed', listener)

    return () => ipcRenderer.removeListener('moor:browser-popout:closed', listener)
  },
  claimAmbientCue: key => ipcRenderer.invoke('moor:ambient:claim', key),
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('moor:wake-indicator:get'),
    setState: state => ipcRenderer.send('moor:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('moor:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('moor:wake-indicator:state', listener)
    }
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('moor:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('moor:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('moor:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('moor:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('moor:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('moor:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('moor:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('moor:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('moor:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('moor:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('moor:pet-overlay:control', listener)
    }
  },
  // HUD mode: the chrome-free floating chat. A full app renderer (own gateway)
  // sized as a floating bar, so it mounts the real composer. Main owns the
  // window; `onChanged` keeps every window's toggle truthful.
  hud: {
    nativeDrag: hudNativeDrag,
    windowing: {
      clientPlacement: hudWindowing?.clientPlacement !== false,
      controlDrag: hudWindowing?.controlDrag === true,
      nativeDrag: hudNativeDrag,
      solid: hudWindowing?.solid === true,
      workspaceTransfer: hudWindowing?.workspaceTransfer === true
    },
    open: request => ipcRenderer.invoke('moor:hud:open', request),
    close: () => ipcRenderer.invoke('moor:hud:close'),
    setIgnoreMouse: ignore => ipcRenderer.send('moor:hud:ignore-mouse', ignore),
    beginMove: () => ipcRenderer.send('moor:hud:begin-move'),
    endMove: () => ipcRenderer.send('moor:hud:end-move'),
    moveBy: delta => ipcRenderer.send('moor:hud:move-by', delta),
    setWorkspaceTransfer: transferring => ipcRenderer.send('moor:hud:workspace-transfer', transferring),
    setBounds: bounds => ipcRenderer.send('moor:hud:set-bounds', bounds),
    resetLayout: () => ipcRenderer.invoke('moor:hud:reset-layout'),
    // Whether the band covers the window below the bar. Main pairs it with the
    // user's translucency setting to decide the native frost (macOS vibrancy /
    // Windows 11 DWM backdrop) — see hudFrostFor.
    setFrost: showing => ipcRenderer.invoke('moor:hud:frost', showing),
    // The HUD tells main which session it is on; main hands that back to the
    // app window when the HUD closes, so the app can re-home onto it.
    setSession: sessionId => ipcRenderer.send('moor:hud:session', sessionId),
    onGoto: callback => {
      const listener = (_event, sessionId) => callback(sessionId)
      ipcRenderer.on('moor:hud:goto', listener)

      return () => ipcRenderer.removeListener('moor:hud:goto', listener)
    },
    onChanged: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('moor:hud:changed', listener)

      return () => ipcRenderer.removeListener('moor:hud:changed', listener)
    },
    // Linux only, and silent elsewhere: where the cursor is, in page
    // coordinates, or null when it has left the window. Stands in for the
    // mousemove that `setIgnoreMouseEvents(true, { forward: true })` delivers on
    // macOS and Windows but not here.
    onCursor: callback => {
      const listener = (_event, point) => callback(point)
      ipcRenderer.on('moor:hud:cursor', listener)

      return () => ipcRenderer.removeListener('moor:hud:cursor', listener)
    },
    // Main's game-overlay watch: whether a fullscreen app (a game) is under
    // the HUD, so the renderer can step back to the low-opacity overlay
    // treatment while one owns the screen.
    onGameOverlay: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('moor:hud:game-overlay', listener)

      return () => ipcRenderer.removeListener('moor:hud:game-overlay', listener)
    }
  },
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('moor:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('moor:quick-entry:settings:set', patch),
    submit: payload => ipcRenderer.send('moor:quick-entry:submit', payload),
    dismiss: () => ipcRenderer.send('moor:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('moor:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('moor:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('moor:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('moor:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('moor:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('moor:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('moor:quick-entry:shown', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('moor:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('moor:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('moor:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('moor:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('moor:connection-config:test', payload),
  // Opt-in OS-keychain encryption for stored gateway secrets (default off —
  // see secret-storage-policy.ts). get never touches the OS keychain.
  getSecretStorageEncryption: () => ipcRenderer.invoke('moor:secret-storage:get'),
  setSecretStorageEncryption: (on: boolean) => ipcRenderer.invoke('moor:secret-storage:set', on),
  // v2 multi-connection registry: named agent sources (local / remote / cloud / ssh).
  connections: {
    list: () => ipcRenderer.invoke('moor:connections:list'),
    save: payload => ipcRenderer.invoke('moor:connections:save', payload),
    remove: id => ipcRenderer.invoke('moor:connections:remove', id),
    setPrimary: id => ipcRenderer.invoke('moor:connections:set-primary', id),
    setLaunchMode: mode => ipcRenderer.invoke('moor:connections:set-launch-mode', mode),
    setLastUsed: id => ipcRenderer.invoke('moor:connections:set-last-used', id),
    test: id => ipcRenderer.invoke('moor:connections:test', id),
    updateManaged: id => ipcRenderer.invoke('moor:connections:update-managed', id),
    // Fan out `moor update` to every eligible registered connection.
    // Optional excludeIds skips rows the caller updates through another path.
    updateAll: options => ipcRenderer.invoke('moor:connections:update-all', options),
    // Registry lifecycle push (main → renderer): a connection was removed or
    // materially edited, so secondaries scoped to it must be disposed (and,
    // for edits, re-dialed at the new target).
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('moor:connections:changed', listener)

      return () => ipcRenderer.removeListener('moor:connections:changed', listener)
    }
  },
  sshConfigHosts: () => ipcRenderer.invoke('moor:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('moor:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('moor:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('moor:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('moor:connection-config:oauth-logout', remoteUrl),
  // Moor Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('moor:cloud:status'),
    login: () => ipcRenderer.invoke('moor:cloud:login'),
    logout: () => ipcRenderer.invoke('moor:cloud:logout'),
    discover: org => ipcRenderer.invoke('moor:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('moor:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    get: () => ipcRenderer.invoke('moor:profile:get'),
    remember: name => ipcRenderer.invoke('moor:profile:remember', name),
    set: name => ipcRenderer.invoke('moor:profile:set', name)
  },
  api: request => ipcRenderer.invoke('moor:api', request),
  notify: payload => ipcRenderer.invoke('moor:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('moor:requestMicrophoneAccess'),
  readWindowBelow: () => ipcRenderer.invoke('moor:window:readBelow'),
  readFileDataUrl: filePath => ipcRenderer.invoke('moor:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('moor:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('moor:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('moor:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('moor:readFileText', filePath),
  readPluginSource: (filePath: string) => ipcRenderer.invoke('moor:readPluginSource', filePath),
  selectPaths: options => ipcRenderer.invoke('moor:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('moor:selectSavePath', options),
  writeClipboard: text => ipcRenderer.invoke('moor:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('moor:readClipboard'),
  saveGatewayFile: payload => ipcRenderer.invoke('moor:saveGatewayFile', payload),
  saveImageFromUrl: url => ipcRenderer.invoke('moor:saveImageFromUrl', url),
  contextMenuEdit: command => ipcRenderer.invoke('moor:context-menu:edit', command),
  contextMenuCopyImage: () => ipcRenderer.invoke('moor:context-menu:copy-image'),
  contextMenuSpellcheck: action => ipcRenderer.invoke('moor:context-menu:spellcheck', action),
  contextMenuGuestAddWord: payload => ipcRenderer.invoke('moor:context-menu:guest-add-word', payload),
  onContextMenuSpellcheck: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('moor:context-menu-spellcheck', listener)

    return () => ipcRenderer.removeListener('moor:context-menu-spellcheck', listener)
  },
  saveImageBuffer: (data, ext, name) => ipcRenderer.invoke('moor:saveImageBuffer', { data, ext, name }),
  capturePreview: payload => ipcRenderer.invoke('moor:capturePreview', payload),
  saveClipboardImage: () => ipcRenderer.invoke('moor:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('moor:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('moor:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('moor:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('moor:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('moor:active-work', payload),
  setTitleBarTheme: payload => ipcRenderer.send('moor:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('moor:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('moor:translucency', payload),
  setKeepAwake: on => ipcRenderer.send('moor:keep-awake', on),
  setDisableF12: blocked => ipcRenderer.send('moor:devtools:disable-f12', blocked),
  setPreviewShortcutActive: active => ipcRenderer.send('moor:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('moor:openExternal', url),
  mcpOauth: {
    // One-shot loopback listener for MCP OAuth against remote backends: bind
    // on this machine, hand redirectUri to mcp.servers.oauth.start, then wait
    // for the provider redirect and relay code/state via oauth.callback.
    listen: () => ipcRenderer.invoke('moor:mcp-oauth:listen'),
    wait: (id, timeoutMs) => ipcRenderer.invoke('moor:mcp-oauth:wait', id, timeoutMs),
    cancel: id => ipcRenderer.invoke('moor:mcp-oauth:cancel', id)
  },
  openPreviewInBrowser: url => ipcRenderer.invoke('moor:openPreviewInBrowser', url),
  reachPreviewUrl: url => ipcRenderer.invoke('moor:preview:reach', url),
  setActiveConnectionRoute: route => ipcRenderer.send('moor:connection:active-route', route),
  fetchLinkTitle: url => ipcRenderer.invoke('moor:fetchLinkTitle', url),
  resolveFavicon: url => ipcRenderer.invoke('moor:resolveFavicon', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('moor:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('moor:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('moor:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('moor:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('moor:zoom:get'),
    // Synchronous zoom factor (1 = 100%). Coordinate math needs it in the
    // same tick as the event it converts, so no IPC round-trip here.
    factor: () => webFrame.getZoomFactor(),
    setPercent: percent => ipcRenderer.send('moor:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('moor:zoom:changed', listener)

      return () => ipcRenderer.removeListener('moor:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('moor:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('moor:logs:recent'),
  // Fire-and-forget: persists a renderer error-boundary catch (with component
  // stack) to desktop.log so crashes survive the window (#79428).
  reportRendererError: report => ipcRenderer.send('moor:logs:renderer-error', report),
  readDir: dirPath => ipcRenderer.invoke('moor:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('moor:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('moor:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('moor:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('moor:fs:desktopPluginsRoot'),
  logsRoot: () => ipcRenderer.invoke('moor:fs:logsRoot'),
  agentPluginsRoot: () => ipcRenderer.invoke('moor:fs:agentPluginsRoot'),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('moor:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('moor:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('moor:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('moor:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('moor:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('moor:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('moor:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('moor:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('moor:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('moor:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('moor:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('moor:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('moor:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('moor:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('moor:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('moor:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('moor:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('moor:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('moor:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('moor:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('moor:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('moor:git:review:shipInfo', repoPath),
      prList: (repoPath, branches, numbers) =>
        ipcRenderer.invoke('moor:git:review:prList', repoPath, branches, numbers),
      fetchPrComment: (repoPath, url) => ipcRenderer.invoke('moor:git:review:fetchPrComment', repoPath, url),
      createPr: repoPath => ipcRenderer.invoke('moor:git:review:createPr', repoPath)
    }
  },
  terminal: {
    attach: id => ipcRenderer.invoke('moor:terminal:attach', id),
    cwd: id => ipcRenderer.invoke('moor:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('moor:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('moor:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('moor:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('moor:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `moor:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `moor:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('moor:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('moor:close-preview-requested', listener)
  },
  onPreviewNav: callback => {
    const listener = (_event, command) => callback(command)
    ipcRenderer.on('moor:preview-nav', listener)

    return () => ipcRenderer.removeListener('moor:preview-nav', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('moor:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('moor:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('moor:open-updates', listener)

    return () => ipcRenderer.removeListener('moor:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('moor:deep-link', listener)

    return () => ipcRenderer.removeListener('moor:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('moor:deep-link-ready'),
  probePluginRepo: payload => ipcRenderer.invoke('moor:plugin:probe', payload),
  installDesktopPlugin: payload => ipcRenderer.invoke('moor:plugin:installDesktop', payload),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('moor:window-state-changed', listener)

    return () => ipcRenderer.removeListener('moor:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('moor:focus-session', listener)

    return () => ipcRenderer.removeListener('moor:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('moor:notification-action', listener)

    return () => ipcRenderer.removeListener('moor:notification-action', listener)
  },
  onNotificationActivate: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('moor:notification-activate', listener)

    return () => ipcRenderer.removeListener('moor:notification-activate', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('moor:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('moor:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('moor:backend-exit', listener)

    return () => ipcRenderer.removeListener('moor:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('moor:connection:applied', listener)

    return () => ipcRenderer.removeListener('moor:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('moor:power-resume', listener)

    return () => ipcRenderer.removeListener('moor:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('moor:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('moor:power-battery', listener)

    return () => ipcRenderer.removeListener('moor:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('moor:boot-progress', listener)

    return () => ipcRenderer.removeListener('moor:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('moor:bootstrap:get'),
  continueBootstrapLocal: () => ipcRenderer.invoke('moor:bootstrap:continue-local'),
  recycleBackend: profile => ipcRenderer.invoke('moor:backend:recycle', profile),
  resetBootstrap: () => ipcRenderer.invoke('moor:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('moor:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('moor:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('moor:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('moor:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('moor:version'),
  relaunchApp: () => ipcRenderer.invoke('moor:app:relaunch'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('moor:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('moor:uninstall:summary'),
    run: mode => ipcRenderer.invoke('moor:uninstall:run', { mode })
  },
  updates: {
    check: () => ipcRenderer.invoke('moor:updates:check'),
    apply: opts => ipcRenderer.invoke('moor:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('moor:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('moor:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('moor:updates:progress', listener)

      return () => ipcRenderer.removeListener('moor:updates:progress', listener)
    }
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('moor:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('moor:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('moor:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('moor:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('moor:found-in-page', listener)

    return () => ipcRenderer.removeListener('moor:found-in-page', listener)
  },
  // Main-process `before-input-event` forwards Ctrl/Cmd+F here so renderer
  // can open the FindBar even when the GTK compositor has already grabbed
  // the chord at the windowing layer (#81727).
  onOpenFindBarRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('moor:open-find-bar', listener)

    return () => ipcRenderer.removeListener('moor:open-find-bar', listener)
  }
})
